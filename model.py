from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import calendar
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional

class SchedulingModel:
    def __init__(self):
        self.num_nurses = 0
        self.num_freelancers = 0
        self.nurse_hours = {}  # Dictionary mapping nurse ID to contracted hours
        self.shift_duration = 8  # Default shift duration in hours
        self.shifts = ["M", "P"]  # M: morning, P: afternoon
        self.year = datetime.now().year
        self.month = datetime.now().month
        self.num_days = 0
        self.min_free_weekends = 1  # Minimum free weekends per nurse
        self.max_consecutive_days = 5  # Maximum consecutive workdays
        self.nurse_preferences = {}  # Dictionary mapping nurse ID to their preferences
        self.freelancer_availability = {}  # Dictionary mapping freelancer ID to their availability
        self.hours_flexibility = 8  # Allow 8 hours of flexibility (one shift) above or below contracted hours

    def setup_model(self, year: int, month: int, num_nurses: int, num_freelancers: int, 
                   nurse_hours: Dict[int, int], min_free_weekends: int, max_consecutive_days: int,
                   nurse_preferences: Dict[int, Dict[Tuple[int, str], int]], 
                   freelancer_availability: Dict[int, Dict[Tuple[int, str], int]],
                   hours_flexibility: int = 8):
        """Setup the model with the provided parameters"""
        self.year = year
        self.month = month
        self.num_nurses = num_nurses
        self.num_freelancers = num_freelancers
        self.nurse_hours = nurse_hours
        self.min_free_weekends = min_free_weekends
        self.max_consecutive_days = max_consecutive_days
        self.nurse_preferences = nurse_preferences
        self.freelancer_availability = freelancer_availability
        self.hours_flexibility = hours_flexibility
        
        # Calculate the number of days in the month
        self.num_days = calendar.monthrange(year, month)[1]
        
    def get_weekend_days(self) -> List[Tuple[int, int]]:
        """Return a list of weekend day pairs (Saturday, Sunday) for the month"""
        weekend_pairs = []
        
        for day in range(1, self.num_days + 1):
            date = datetime(self.year, self.month, day)
            # If it's Saturday (5), check if the next day exists and is Sunday
            if date.weekday() == 5 and day + 1 <= self.num_days:
                next_date = datetime(self.year, self.month, day + 1)
                if next_date.weekday() == 6:  # Sunday
                    # Convert to 0-indexed for the model
                    weekend_pairs.append((day - 1, day))
        
        return weekend_pairs
    
    def solve(self) -> Tuple[bool, Optional[pd.DataFrame], Optional[Dict[int, int]], Optional[Dict[int, int]]]:
        """Solve the nurse scheduling problem and return the result"""
        model = cp_model.CpModel()
        
        all_nurses = range(self.num_nurses)
        all_freelancers = range(self.num_freelancers)
        all_employees = range(self.num_nurses + self.num_freelancers)
        all_days = range(self.num_days)
        all_shifts = range(len(self.shifts))
        
        # Create shift variables
        # shifts[(e, d, s)]: employee 'e' works shift 's' on day 'd'
        shifts = {}
        for e in all_employees:
            for d in all_days:
                for s in all_shifts:
                    shifts[(e, d, s)] = model.new_bool_var(f"shift_e{e}_d{d}_s{s}")
        
        # Each shift each day needs exactly one employee
        for d in all_days:
            for s in all_shifts:
                model.add_exactly_one(shifts[(e, d, s)] for e in all_employees)
        
        # Each employee works at most one shift per day
        for e in all_employees:
            for d in all_days:
                model.add_at_most_one(shifts[(e, d, s)] for s in all_shifts)
        
        # Ensure nurse contracted hours with flexibility
        for n in all_nurses:
            worked_hours = sum(shifts[(n, d, s)] * self.shift_duration 
                             for d in all_days for s in all_shifts)
            target_hours = self.nurse_hours[n]
            
            # Allow flexibility within a range
            model.add(worked_hours >= target_hours - self.hours_flexibility)
            model.add(worked_hours <= target_hours + self.hours_flexibility)
        
        # Freelancers can only work when available
        for f_idx, f in enumerate(range(self.num_nurses, self.num_nurses + self.num_freelancers)):
            for d in all_days:
                for s in all_shifts:
                    day_key = (d + 1, self.shifts[s])  # Convert to 1-indexed days
                    if day_key not in self.freelancer_availability[f_idx] or self.freelancer_availability[f_idx][day_key] == 0:
                        model.add(shifts[(f, d, s)] == 0)
        
        # No more than max_consecutive_days worked in a row
        for e in all_employees:
            for start_day in range(self.num_days - self.max_consecutive_days):
                # Sum of shifts worked in max_consecutive_days + 1 consecutive days
                consecutive_shifts = []
                for d in range(start_day, start_day + self.max_consecutive_days + 1):
                    if d < self.num_days:  # Ensure we don't go beyond the month
                        for s in all_shifts:
                            consecutive_shifts.append(shifts[(e, d, s)])
                model.add(sum(consecutive_shifts) <= self.max_consecutive_days)
        
        # No back-to-back shifts (P followed by M)
        for e in all_employees:
            for d in range(self.num_days - 1):
                # If employee works afternoon shift (index 1) on day d, they can't work morning shift (index 0) on day d+1
                model.add(shifts[(e, d, 1)] + shifts[(e, d+1, 0)] <= 1)
        
        # Get weekend pairs (Saturday, Sunday)
        weekend_pairs = self.get_weekend_days()
        print(f"Weekend pairs: {weekend_pairs}")  # Debug info
        
        # Enforce minimum free weekends for nurses
        for n in all_nurses:
            weekend_is_free = []
            for sat_idx, sun_idx in weekend_pairs:
                # Create a variable for whether this weekend is free for this nurse
                is_free = model.new_bool_var(f"weekend_free_n{n}_w{sat_idx//7}")
                
                # A weekend is free if both Saturday and Sunday are free
                sat_shifts = sum(shifts[(n, sat_idx, s)] for s in all_shifts)
                sun_shifts = sum(shifts[(n, sun_idx, s)] for s in all_shifts)
                
                # Use linear constraints instead of boolean operations
                # is_free = 1 if and only if sat_shifts = 0 and sun_shifts = 0
                model.add(sat_shifts + sun_shifts <= 2 * (1 - is_free))
                model.add(sat_shifts + sun_shifts >= 1 - is_free)
                
                weekend_is_free.append(is_free)
            
            # Ensure at least min_free_weekends are free
            if weekend_is_free:
                model.add(sum(weekend_is_free) >= self.min_free_weekends)
        
        # Objective function with normalized components and weights (40%, 20%, 40%)
        objective_terms = []
        
        # Calculate maximum possible values for normalization
        max_nurse_pref = 0
        for n in all_nurses:
            max_nurse_pref += len(self.nurse_preferences.get(n, {}))
        
        max_freelancer_avail = 0
        for f_idx in range(self.num_freelancers):
            max_freelancer_avail += len(self.freelancer_availability.get(f_idx, {}))
        
        max_free_weekends = len(weekend_pairs) * self.num_nurses
        
        # Avoid division by zero
        max_nurse_pref = max(max_nurse_pref, 1)
        max_freelancer_avail = max(max_freelancer_avail, 1)
        max_free_weekends = max(max_free_weekends, 1)
        
        # Calculate scaling factors (instead of division)
        # Scale to keep the proportion 40/20/40
        nurse_pref_scale = 400.0 / max_nurse_pref  # 40% weight
        freelancer_avail_scale = 200.0 / max_freelancer_avail  # 20% weight
        free_weekends_scale = 400.0 / max_free_weekends  # 40% weight
        
        # 1. Nurse preferences (40% weight)
        for n in all_nurses:
            for d in all_days:
                for s in all_shifts:
                    day_key = (d + 1, self.shifts[s])  # Convert to 1-indexed days
                    if day_key in self.nurse_preferences[n]:
                        # Use multiplication with scaling factor instead of division
                        objective_terms.append(shifts[(n, d, s)] * self.nurse_preferences[n][day_key] * nurse_pref_scale)
        
        # 2. Freelancer availability (20% weight)
        for f_idx, f in enumerate(range(self.num_nurses, self.num_nurses + self.num_freelancers)):
            for d in all_days:
                for s in all_shifts:
                    day_key = (d + 1, self.shifts[s])  # Convert to 1-indexed days
                    if day_key in self.freelancer_availability[f_idx] and self.freelancer_availability[f_idx][day_key] == 1:
                        # Use multiplication with scaling factor
                        objective_terms.append(shifts[(f, d, s)] * freelancer_avail_scale)
        
        # 3. Free weekends beyond minimum (40% weight)
        for n in all_nurses:
            for is_free in weekend_is_free:
                # Use multiplication with scaling factor
                objective_terms.append(is_free * free_weekends_scale)
        
        # Add the objective function
        if objective_terms:
            model.maximize(sum(objective_terms))
        
        # Create a solver and solve the model
        solver = cp_model.CpSolver()
        
        # Set a time limit to avoid getting stuck (300 seconds = 5 minutes)
        solver.parameters.max_time_in_seconds = 300.0
        
        # Set additional parameters for better solution quality
        solver.parameters.linearization_level = 0
        
        status = solver.solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            # Create a DataFrame with the schedule
            dates = [datetime(self.year, self.month, day+1) for day in all_days]
            
            # Create a dictionary to store hours worked per nurse for summary
            hours_worked = {n: 0 for n in all_nurses}
            
            # Create new schedule format with dates as rows and employees as columns
            # Initialize data with dates
            schedule_data = []
            for d in all_days:
                date = dates[d]
                row_data = {
                    'Data': date.strftime('%d/%m/%Y'),
                    'Giorno': date.strftime('%A'),
                }
                
                # Add employees as columns
                for n in all_nurses:
                    employee_name = f"Infermiere {n+1}"
                    if solver.value(shifts[(n, d, 0)]) == 1:  # Morning shift
                        row_data[employee_name] = "Mattino"
                        hours_worked[n] += self.shift_duration
                    elif solver.value(shifts[(n, d, 1)]) == 1:  # Afternoon shift
                        row_data[employee_name] = "Pomeriggio"
                        hours_worked[n] += self.shift_duration
                    else:
                        row_data[employee_name] = "Riposo"
                
                # Add freelancers as columns
                for f_idx, f in enumerate(range(self.num_nurses, self.num_nurses + self.num_freelancers)):
                    employee_name = f"Freelancer {f_idx+1}"
                    if solver.value(shifts[(f, d, 0)]) == 1:  # Morning shift
                        row_data[employee_name] = "Mattino"
                    elif solver.value(shifts[(f, d, 1)]) == 1:  # Afternoon shift
                        row_data[employee_name] = "Pomeriggio"
                    else:
                        row_data[employee_name] = "Riposo"
                
                schedule_data.append(row_data)
            
            # Create a DataFrame
            schedule_df = pd.DataFrame(schedule_data)
            
            # Calculate free weekends for each nurse
            free_weekends = {n: 0 for n in all_nurses}
            for n in all_nurses:
                for sat_idx, sun_idx in weekend_pairs:
                    sat_free = True
                    sun_free = True
                    
                    for s in all_shifts:
                        if solver.value(shifts[(n, sat_idx, s)]) == 1:
                            sat_free = False
                        if solver.value(shifts[(n, sun_idx, s)]) == 1:
                            sun_free = False
                    
                    if sat_free and sun_free:
                        free_weekends[n] += 1
            
            # Print hours worked summary
            print("Ore lavorate per infermiere:")
            for n in all_nurses:
                print(f"Infermiere {n+1}: {hours_worked[n]} ore (obiettivo: {self.nurse_hours[n]} ± {self.hours_flexibility})")
            
            # Print free weekends summary
            print("Weekend liberi per infermiere:")
            for n in all_nurses:
                print(f"Infermiere {n+1}: {free_weekends[n]} weekend liberi (minimo richiesto: {self.min_free_weekends})")
            
            return True, schedule_df, hours_worked, free_weekends
        else:
            print(f"Solve status: {status}")
            if status == cp_model.INFEASIBLE:
                print("Il problema non ammette soluzioni con i vincoli specificati.")
            elif status == cp_model.MODEL_INVALID:
                print("Il modello è invalido.")
            elif status == cp_model.UNKNOWN:
                print("Il solutore non è riuscito a trovare una soluzione entro il tempo limite.")
            return False, None, None, None
    
    def export_to_excel(self, schedule_df, filename="schedule.xlsx", hours_worked=None, nurse_hours=None, hours_flexibility=None, free_weekends=None, min_free_weekends=None):
        """Export the schedule to an Excel file"""
        writer = pd.ExcelWriter(filename, engine='xlsxwriter')
        schedule_df.to_excel(writer, sheet_name='Pianificazione', index=False)
        
        # Add summary sheet if we have hours and weekends data
        if hours_worked and nurse_hours and free_weekends:
            # Create a DataFrame for summary
            summary_data = []
            for nurse_id in range(len(nurse_hours)):
                target_hours = nurse_hours[nurse_id]
                actual_hours = hours_worked[nurse_id] if nurse_id in hours_worked else 0
                target_weekends = min_free_weekends or 1
                actual_weekends = free_weekends[nurse_id] if nurse_id in free_weekends else 0
                hours_diff = actual_hours - target_hours
                flex = hours_flexibility if hours_flexibility is not None else 0
                
                summary_data.append({
                    'Infermiere': f"Infermiere {nurse_id + 1}",
                    'Ore Contrattuali': target_hours,
                    'Ore Pianificate': actual_hours,
                    'Differenza Ore': hours_diff,
                    'Entro Flessibilità': "Sì" if abs(hours_diff) <= flex else "No",
                    'Weekend Liberi': actual_weekends,
                    'Weekends Minimi': target_weekends,
                    'Weekends OK': "Sì" if actual_weekends >= target_weekends else "No"
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Riepilogo', index=False)
        
        # Add hours worked sheet (legacy)
        if hours_worked and nurse_hours:
            # Create a DataFrame for hours worked
            hours_data = []
            for nurse_id, hours in hours_worked.items():
                target_hours = nurse_hours[nurse_id]
                flex = hours_flexibility if hours_flexibility is not None else 0
                diff = hours - target_hours
                
                hours_data.append({
                    'Infermiere': f"Infermiere {nurse_id + 1}",
                    'Ore Contrattuali': target_hours,
                    'Ore Lavorate': hours,
                    'Differenza': diff,
                    'Entro Flessibilità': "Sì" if abs(diff) <= flex else "No"
                })
            
            hours_df = pd.DataFrame(hours_data)
            hours_df.to_excel(writer, sheet_name='Ore Lavorate', index=False)
        
        # Format the Excel file
        workbook = writer.book
        worksheet = writer.sheets['Pianificazione']
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1})
        
        weekend_format = workbook.add_format({
            'fg_color': '#FFCCCC',
            'border': 1})
        
        morning_format = workbook.add_format({
            'fg_color': '#FFEB99',
            'border': 1,
            'align': 'center'})
        
        afternoon_format = workbook.add_format({
            'fg_color': '#99CCFF',
            'border': 1,
            'align': 'center'})
        
        rest_format = workbook.add_format({
            'fg_color': '#D9D9D9',
            'font_color': '#777777',
            'border': 1,
            'align': 'center'})
        
        # Set column widths
        worksheet.set_column('A:A', 12)  # Date
        worksheet.set_column('B:B', 10)  # Day of week
        
        # Set width for all employee columns
        for col_idx in range(2, len(schedule_df.columns)):
            worksheet.set_column(col_idx, col_idx, 12)
        
        # Set the header format
        for col_num, value in enumerate(schedule_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Apply conditional formatting to shift cells and highlight weekends
        for row_num, row in enumerate(schedule_df.iterrows(), start=1):
            # Highlight weekend rows
            if row[1]['Giorno'] in ['Saturday', 'Sunday', 'Sabato', 'Domenica']:
                worksheet.set_row(row_num, None, weekend_format)
            
            # Apply shift formatting to each employee cell
            for col_num, (col_name, cell_value) in enumerate(row[1].items()):
                if col_name not in ['Data', 'Giorno']:
                    # Get the cell position
                    cell_pos = f"{chr(65 + col_num)}{row_num + 1}"  # A1, B1, etc.
                    
                    # Apply the appropriate format based on shift type
                    if cell_value == "Mattino":
                        worksheet.write(row_num, col_num, cell_value, morning_format)
                    elif cell_value == "Pomeriggio":
                        worksheet.write(row_num, col_num, cell_value, afternoon_format)
                    elif cell_value == "Riposo":
                        worksheet.write(row_num, col_num, cell_value, rest_format)
        
        # Format the summary sheet if available
        if hours_worked and nurse_hours and free_weekends:
            summary_worksheet = writer.sheets['Riepilogo']
            
            # Set column widths
            summary_worksheet.set_column('A:A', 15)  # Infermiere
            summary_worksheet.set_column('B:B', 15)  # Ore Contrattuali
            summary_worksheet.set_column('C:C', 15)  # Ore Pianificate
            summary_worksheet.set_column('D:D', 15)  # Differenza Ore
            summary_worksheet.set_column('E:E', 15)  # Entro Flessibilità
            summary_worksheet.set_column('F:F', 15)  # Weekend Liberi
            summary_worksheet.set_column('G:G', 15)  # Weekends Minimi
            summary_worksheet.set_column('H:H', 15)  # Weekends OK
            
            # Set the header format
            for col_num, value in enumerate(summary_df.columns.values):
                summary_worksheet.write(0, col_num, value, header_format)
            
            # Define formats for conditional formatting
            good_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
            bad_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            
            # Apply conditional formatting to the "Entro Flessibilità" column
            summary_worksheet.conditional_format('E2:E100', {'type': 'cell',
                                                          'criteria': '==',
                                                          'value': '"Sì"',
                                                          'format': good_format})
            
            summary_worksheet.conditional_format('E2:E100', {'type': 'cell',
                                                          'criteria': '==',
                                                          'value': '"No"',
                                                          'format': bad_format})
            
            # Apply conditional formatting to the "Weekends OK" column
            summary_worksheet.conditional_format('H2:H100', {'type': 'cell',
                                                          'criteria': '==',
                                                          'value': '"Sì"',
                                                          'format': good_format})
            
            summary_worksheet.conditional_format('H2:H100', {'type': 'cell',
                                                          'criteria': '==',
                                                          'value': '"No"',
                                                          'format': bad_format})
        
        # Format the hours worked sheet if available
        if hours_worked and nurse_hours:
            hours_worksheet = writer.sheets['Ore Lavorate']
            
            # Set column widths
            hours_worksheet.set_column('A:A', 15)
            hours_worksheet.set_column('B:B', 15)
            hours_worksheet.set_column('C:C', 15)
            hours_worksheet.set_column('D:D', 15)
            hours_worksheet.set_column('E:E', 15)
            
            # Set the header format
            for col_num, value in enumerate(hours_df.columns.values):
                hours_worksheet.write(0, col_num, value, header_format)
            
            # Define conditional formatting
            good_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
            bad_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            
            # Apply conditional formatting to the "Entro Flessibilità" column
            hours_worksheet.conditional_format('E2:E100', {'type': 'cell',
                                                         'criteria': '==',
                                                         'value': '"Sì"',
                                                         'format': good_format})
            
            hours_worksheet.conditional_format('E2:E100', {'type': 'cell',
                                                         'criteria': '==',
                                                         'value': '"No"',
                                                         'format': bad_format})
        
        writer.close()
        return filename
