from ortools.sat.python import cp_model
from datetime import datetime, timedelta
import calendar
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import io

class SchedulingModel:
    def __init__(self):
        self.num_nurses = 0
        self.num_freelancers = 0
        self.max_nurse_hours = {}  # Dictionary mapping nurse ID to maximum regular hours
        self.max_overhours = 0  # Maximum overhours (in shifts) each nurse can work
        self.shift_duration = 8  # Default shift duration in hours
        self.shifts = ["M", "P"]  # M: morning, P: afternoon
        self.year = datetime.now().year
        self.month = datetime.now().month
        self.num_days = 0
        self.min_free_weekends = 1  # Minimum free weekends per nurse
        self.max_consecutive_days = 5  # Maximum consecutive workdays
        self.nurse_preferences = {}  # Dictionary mapping nurse ID to their preferences
        self.freelancer_availability = {}  # Dictionary mapping freelancer ID to their availability
        self.work_rest_ratio = 3.0  # Default work-to-rest ratio
        # Cost parameters (hardcoded)
        self.nurse_regular_cost = 1
        self.freelancer_cost = 1.5
        self.nurse_overhours_cost = 2

    def setup_model(self, year: int, month: int, num_nurses: int, num_freelancers: int, 
                   max_nurse_hours: Dict[int, int], min_free_weekends: int, max_consecutive_days: int,
                   nurse_preferences: Dict[int, Dict[Tuple[int, str], int]], 
                   freelancer_availability: Dict[int, Dict[Tuple[int, str], int]],
                   max_overhours: int = 1, work_rest_ratio: float = 3.0):
        """Setup the model with the provided parameters"""
        self.year = year
        self.month = month
        self.num_nurses = num_nurses
        self.num_freelancers = num_freelancers
        self.max_nurse_hours = max_nurse_hours
        self.min_free_weekends = min_free_weekends
        self.max_consecutive_days = max_consecutive_days
        self.nurse_preferences = nurse_preferences
        self.freelancer_availability = freelancer_availability
        self.max_overhours = max_overhours
        self.work_rest_ratio = work_rest_ratio
        
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
        
        # Create overhours variables for nurses
        # overhour_shifts[(n, d, s)]: nurse 'n' works shift 's' on day 'd' as overhours
        overhour_shifts = {}
        for n in all_nurses:
            for d in all_days:
                for s in all_shifts:
                    overhour_shifts[(n, d, s)] = model.new_bool_var(f"overhour_n{n}_d{d}_s{s}")
        
        # Each shift each day needs exactly one employee
        for d in all_days:
            for s in all_shifts:
                model.add_exactly_one(shifts[(e, d, s)] for e in all_employees)
        
        # Each employee works at most one shift per day
        for e in all_employees:
            for d in all_days:
                model.add_at_most_one(shifts[(e, d, s)] for s in all_shifts)
        
        # Track regular and overtime hours for nurses
        regular_hours = {}
        overtime_hours = {}
        
        for n in all_nurses:
            # Calculate total shifts worked
            total_shifts = sum(shifts[(n, d, s)] for d in all_days for s in all_shifts)
            
            # Calculate maximum number of regular shifts
            max_regular_shifts = self.max_nurse_hours[n] // self.shift_duration
            
            # Define regular and overtime shifts
            regular_hours[n] = model.new_int_var(0, max_regular_shifts, f"regular_hours_n{n}")
            overtime_hours[n] = model.new_int_var(0, self.max_overhours, f"overtime_hours_n{n}")
            
            # Total shifts = regular + overtime
            model.add(regular_hours[n] + overtime_hours[n] == total_shifts)
            
            # Regular hours cannot exceed maximum
            model.add(regular_hours[n] <= max_regular_shifts)
            
            # Overtime hours cannot exceed maximum overhours
            model.add(overtime_hours[n] <= self.max_overhours)
            
            # Ensure overtime shifts are properly counted
            overtime_shift_count = sum(overhour_shifts[(n, d, s)] for d in all_days for s in all_shifts)
            model.add(overtime_hours[n] == overtime_shift_count)
            
            # Ensure overhour_shifts are a subset of shifts
            for d in all_days:
                for s in all_shifts:
                    # If it's an overhour shift, it must also be a regular shift
                    model.add(overhour_shifts[(n, d, s)] <= shifts[(n, d, s)])
        
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
        
        # Sliding window constraint: in any 14-day period, maintain the specified work-to-rest ratio
        window_size = 14
        # Calculate max work days based on the ratio: work / (work + rest) = ratio
        # In a 14-day window with work + rest = 14:
        # work / 14 = ratio
        # So work = 14 * ratio / (1 + ratio)
        # For a 3:1 ratio, this gives 10.5 days, which we round down to 10
        max_work_days_in_window = min(int(window_size * self.work_rest_ratio / (1 + self.work_rest_ratio)), window_size - 1)
        
        for e in all_employees:
            # For each possible starting day of a 14-day window
            for start_day in range(self.num_days - window_size + 1):
                # Sum of shifts worked in this 14-day window
                window_shifts = []
                for d in range(start_day, start_day + window_size):
                    if d < self.num_days:  # Ensure we don't go beyond the month
                        for s in all_shifts:
                            window_shifts.append(shifts[(e, d, s)])
                
                # Ensure the number of work days in this window is at most max_work_days_in_window
                model.add(sum(window_shifts) <= max_work_days_in_window)
        
        # No back-to-back shifts (P followed by M)
        for e in all_employees:
            for d in range(self.num_days - 1):
                # If employee works afternoon shift (index 1) on day d, they can't work morning shift (index 0) on day d+1
                model.add(shifts[(e, d, 1)] + shifts[(e, d+1, 0)] <= 1)
        
        # Get weekend pairs (Saturday, Sunday)
        weekend_pairs = self.get_weekend_days()
        print(f"Weekend pairs: {weekend_pairs}")  # Debug info
        
        # Enforce minimum free weekends for nurses
        weekend_is_free = {}
        for n in all_nurses:
            weekend_is_free[n] = []
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
                
                weekend_is_free[n].append(is_free)
            
            # Ensure at least min_free_weekends are free
            if weekend_is_free[n]:
                model.add(sum(weekend_is_free[n]) >= self.min_free_weekends)

        # Create objective function with weighted components
        objective_terms = []
        
        # Calculate maximum possible values for normalization
        max_nurse_pref = sum(len(self.nurse_preferences.get(n, {})) for n in all_nurses)
        max_free_weekends = len(weekend_pairs) * self.num_nurses
        
        # Avoid division by zero
        max_nurse_pref = max(max_nurse_pref, 1)
        max_free_weekends = max(max_free_weekends, 1)
        
        # 1. Nurse preferences - MAXIMIZE (30% weight)
        nurse_pref_scale = 3000.0 / max_nurse_pref
        for n in all_nurses:
            for d in all_days:
                for s in all_shifts:
                    day_key = (d + 1, self.shifts[s])  # Convert to 1-indexed days
                    if day_key in self.nurse_preferences[n]:
                        objective_terms.append(shifts[(n, d, s)] * self.nurse_preferences[n][day_key] * nurse_pref_scale)
        
        # 2. Assignment costs - MINIMIZE (40% weight)
        # We'll negate these terms since we're maximizing the objective
        # Regular nurse hours
        for n in all_nurses:
            regular_shifts_cost = regular_hours[n] * self.nurse_regular_cost
            objective_terms.append(-regular_shifts_cost * 40)  # Negative because we want to minimize cost
        
        # Nurse overhours
        for n in all_nurses:
            overhours_cost = overtime_hours[n] * self.nurse_overhours_cost
            objective_terms.append(-overhours_cost * 40)  # Negative because we want to minimize cost
        
        # Freelancer costs
        for f in range(self.num_nurses, self.num_nurses + self.num_freelancers):
            freelancer_shifts = sum(shifts[(f, d, s)] for d in all_days for s in all_shifts)
            freelancer_cost = freelancer_shifts * self.freelancer_cost
            objective_terms.append(-freelancer_cost * 40)  # Negative because we want to minimize cost
        
        # 3. Free weekends - MAXIMIZE (30% weight)
        free_weekends_scale = 3000.0 / max_free_weekends
        for n in all_nurses:
            for is_free in weekend_is_free.get(n, []):
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
            
            # Create dictionaries to store hours worked per nurse and freelancer
            hours_worked = {n: 0 for n in all_nurses}
            regular_hours_worked = {n: 0 for n in all_nurses}
            overhours_worked = {n: 0 for n in all_nurses}
            
            # Create new schedule format with dates as rows and employees as columns
            # Initialize data with dates
            schedule_data = []
            for d in all_days:
                date = dates[d]
                row_data = {
                    'Data': date.strftime('%d/%m/%Y'),
                    'Giorno': date.strftime('%A'),
                }
                
                # Add nurses as columns
                for n in all_nurses:
                    employee_name = f"Infermiere {n+1}"
                    if solver.value(shifts[(n, d, 0)]) == 1:  # Morning shift
                        is_overhour = solver.value(overhour_shifts[(n, d, 0)]) == 1
                        row_data[employee_name] = "M (S)" if is_overhour else "M"
                        hours_worked[n] += self.shift_duration
                        if is_overhour:
                            overhours_worked[n] += self.shift_duration
                        else:
                            regular_hours_worked[n] += self.shift_duration
                    elif solver.value(shifts[(n, d, 1)]) == 1:  # Afternoon shift
                        is_overhour = solver.value(overhour_shifts[(n, d, 1)]) == 1
                        row_data[employee_name] = "P (S)" if is_overhour else "P"
                        hours_worked[n] += self.shift_duration
                        if is_overhour:
                            overhours_worked[n] += self.shift_duration
                        else:
                            regular_hours_worked[n] += self.shift_duration
                    else:
                        row_data[employee_name] = "R"
                
                # Add freelancers as columns
                for f_idx, f in enumerate(range(self.num_nurses, self.num_nurses + self.num_freelancers)):
                    employee_name = f"Libero Professionista {f_idx+1}"
                    if solver.value(shifts[(f, d, 0)]) == 1:  # Morning shift
                        row_data[employee_name] = "M"
                    elif solver.value(shifts[(f, d, 1)]) == 1:  # Afternoon shift
                        row_data[employee_name] = "P"
                    else:
                        row_data[employee_name] = "R"
                
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
            
            # Calculate costs
            nurse_regular_cost_total = sum(regular_hours_worked[n] // self.shift_duration * self.nurse_regular_cost for n in all_nurses)
            nurse_overtime_cost_total = sum(overhours_worked[n] // self.shift_duration * self.nurse_overhours_cost for n in all_nurses)
            
            freelancer_shifts_total = 0
            for f in range(self.num_nurses, self.num_nurses + self.num_freelancers):
                for d in all_days:
                    for s in all_shifts:
                        if solver.value(shifts[(f, d, s)]) == 1:
                            freelancer_shifts_total += 1
            
            freelancer_cost_total = freelancer_shifts_total * self.freelancer_cost
            total_cost = nurse_regular_cost_total + nurse_overtime_cost_total + freelancer_cost_total
            
            # Print summary information
            print("Ore lavorate per infermiere:")
            for n in all_nurses:
                reg_hours = regular_hours_worked[n]
                ot_hours = overhours_worked[n]
                print(f"Infermiere {n+1}: {reg_hours} ore regolari, {ot_hours} ore straordinario (max: {self.max_nurse_hours[n]} regolari, {self.max_overhours * self.shift_duration} straordinario)")
            
            print("Weekend liberi per infermiere:")
            for n in all_nurses:
                print(f"Infermiere {n+1}: {free_weekends[n]} weekend liberi (minimo richiesto: {self.min_free_weekends})")
            
            print("Costi totali:")
            print(f"Costo infermieri (ore regolari): {nurse_regular_cost_total}")
            print(f"Costo infermieri (ore straordinario): {nurse_overtime_cost_total}")
            print(f"Costo liberi professionisti: {freelancer_cost_total}")
            print(f"Costo totale: {total_cost}")
            
            # Store cost information in hours_worked dictionary to return it
            hours_worked['regular_cost'] = nurse_regular_cost_total
            hours_worked['overtime_cost'] = nurse_overtime_cost_total
            hours_worked['freelancer_cost'] = freelancer_cost_total
            hours_worked['total_cost'] = total_cost
            
            # Also track regular and overtime hours
            for n in all_nurses:
                hours_worked[f'{n}_regular'] = regular_hours_worked[n]
                hours_worked[f'{n}_overtime'] = overhours_worked[n]
            
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
                    if cell_value == "M":
                        worksheet.write(row_num, col_num, cell_value, morning_format)
                    elif cell_value == "P":
                        worksheet.write(row_num, col_num, cell_value, afternoon_format)
                    elif cell_value == "R":
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

    def export_to_excel_bytes(self, schedule_df, filename="schedule.xlsx", hours_worked=None, nurse_hours=None, hours_flexibility=None, free_weekends=None, min_free_weekends=None):
        """Export the schedule to an Excel file and return the bytes"""
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        
        # Create a transposed version of the schedule for Excel export (days as columns, employees as rows)
        # First, create a list of employees (all columns except Data and Giorno)
        employees = [col for col in schedule_df.columns if col not in ['Data', 'Giorno']]
        
        # Create a new dataframe with employees as rows
        transposed_data = []
        
        # Create day header labels
        day_headers = []
        for idx, row in schedule_df.iterrows():
            day_label = f"{row['Data']} ({row['Giorno'][:3]})"
            day_headers.append(day_label)
        
        # First, create a row for day names
        days_row = {'Dipendente': 'Giorno'}
        for idx, day_header in enumerate(day_headers):
            # Get the original day name from the dataframe
            day_name = schedule_df.iloc[idx]['Giorno']
            days_row[day_header] = day_name
        
        transposed_data.append(days_row)
        
        # Then add one row per employee
        for employee in employees:
            employee_shifts = {'Dipendente': employee}
            
            # Add one column for each day
            for idx, day_header in enumerate(day_headers):
                employee_shifts[day_header] = schedule_df.iloc[idx][employee]
            
            transposed_data.append(employee_shifts)
        
        transposed_df = pd.DataFrame(transposed_data)
        
        # Save the transposed dataframe to Excel
        transposed_df.to_excel(writer, sheet_name='Pianificazione', index=False)
        
        # Add summary sheet if we have hours and weekends data
        if hours_worked and nurse_hours and free_weekends:
            # Create a DataFrame for summary
            summary_data = []
            for nurse_id in range(len(nurse_hours)):
                max_hours = nurse_hours[nurse_id]
                total_hours = hours_worked[nurse_id] if nurse_id in hours_worked else 0
                
                # Get regular and overtime hours if available
                regular_hours = hours_worked.get(f'{nurse_id}_regular', 0)
                overtime_hours = hours_worked.get(f'{nurse_id}_overtime', 0)
                
                target_weekends = min_free_weekends or 1
                actual_weekends = free_weekends[nurse_id] if nurse_id in free_weekends else 0
                max_ot_hours = hours_flexibility if hours_flexibility is not None else 8
                
                # Check if overtime is within limits
                overtime_ok = "Sì" if overtime_hours <= max_ot_hours else "No"
                
                summary_data.append({
                    'Infermiere': f"Infermiere {nurse_id + 1}",
                    'Ore Target': max_hours,
                    'Ore Straordinario': overtime_hours,
                    'Ore Lavorate': total_hours,
                    'Straordinario OK': overtime_ok,
                    'Weekend Liberi': actual_weekends,
                    'Weekends Minimi': target_weekends,
                    'Weekends OK': "Sì" if actual_weekends >= target_weekends else "No"
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Riepilogo', index=False)
        
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
            
        day_row_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#E6E6E6',
            'border': 1})
        
        m_format = workbook.add_format({
            'fg_color': '#ffeb99',
            'border': 1,
            'align': 'center'})
        
        m_overtime_format = workbook.add_format({
            'fg_color': '#ffcc99',
            'border': 1,
            'align': 'center'})
        
        p_format = workbook.add_format({
            'fg_color': '#99CCFF',
            'border': 1,
            'align': 'center'})
        
        p_overtime_format = workbook.add_format({
            'fg_color': '#99CCFF',
            'border': 2,
            'border_color': '#ff6666',
            'align': 'center'})
        
        r_format = workbook.add_format({
            'fg_color': '#D9D9D9',
            'font_color': '#777777',
            'border': 1,
            'align': 'center'})
        
        weekend_format = workbook.add_format({
            'bg_color': '#FFCCCC',
        })
        
        # Set width for employee column
        worksheet.set_column('A:A', 25)  # Employee names
        
        # Set width for day columns
        for col_idx in range(1, len(transposed_df.columns)):
            worksheet.set_column(col_idx, col_idx, 15)
        
        # Set the header format
        for col_num, value in enumerate(transposed_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
            # Apply weekend formatting to headers (highlight Saturday and Sunday)
            if col_num > 0 and ('Sab' in value or 'Dom' in value or 'Sat' in value or 'Sun' in value):
                worksheet.set_column(col_num, col_num, 15, weekend_format)
        
        # Apply conditional formatting to shift cells
        for row_num, row in enumerate(transposed_df.iterrows(), start=1):
            for col_num, (col_name, cell_value) in enumerate(row[1].items()):
                if col_name != 'Dipendente':
                    if row_num == 1:  # This is the day name row
                        # Apply formatting to day names
                        if 'Sabato' in cell_value or 'Domenica' in cell_value or 'Saturday' in cell_value or 'Sunday' in cell_value:
                            day_weekend_format = workbook.add_format({
                                'bold': True,
                                'fg_color': '#FFCCCC',
                                'border': 1,
                                'align': 'center'
                            })
                            worksheet.write(row_num, col_num, cell_value, day_weekend_format)
                        else:
                            worksheet.write(row_num, col_num, cell_value, day_row_format)
                    else:
                        # Apply the appropriate format based on shift type for regular rows
                        if cell_value == "M":
                            worksheet.write(row_num, col_num, cell_value, m_format)
                        elif cell_value == "M (S)":
                            worksheet.write(row_num, col_num, cell_value, m_overtime_format)
                        elif cell_value == "P":
                            worksheet.write(row_num, col_num, cell_value, p_format)
                        elif cell_value == "P (S)":
                            worksheet.write(row_num, col_num, cell_value, p_overtime_format)
                        elif cell_value == "R":
                            worksheet.write(row_num, col_num, cell_value, r_format)
                else:
                    # Write employee name or day label
                    if row_num == 1:  # This is the day name row
                        worksheet.write(row_num, col_num, cell_value, day_row_format)
                    else:
                        worksheet.write(row_num, col_num, cell_value)
        
        # Format the summary sheet if available
        if hours_worked and nurse_hours and free_weekends:
            summary_worksheet = writer.sheets['Riepilogo']
            
            # Set column widths
            summary_worksheet.set_column('A:A', 15)  # Infermiere
            summary_worksheet.set_column('B:B', 15)  # Ore Target
            summary_worksheet.set_column('C:C', 15)  # Ore Straordinario
            summary_worksheet.set_column('D:D', 15)  # Ore Lavorate
            summary_worksheet.set_column('E:E', 15)  # Straordinario OK
            summary_worksheet.set_column('F:F', 15)  # Weekend Liberi
            summary_worksheet.set_column('G:G', 15)  # Weekends Minimi
            summary_worksheet.set_column('H:H', 15)  # Weekends OK
            
            # Set the header format
            for col_num, value in enumerate(summary_df.columns.values):
                summary_worksheet.write(0, col_num, value, header_format)
            
            # Define formats for conditional formatting
            good_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
            bad_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            
            # Apply conditional formatting to the "Straordinario OK" column
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
        
        writer.close()
        
        # Get the bytes
        output.seek(0)
        return output.getvalue()
