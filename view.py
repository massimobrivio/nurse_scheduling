import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar
import io

class SchedulingView:
    def __init__(self):
        st.set_page_config(
            page_title="Pianificazione Turni Infermieri",
            page_icon="🏥",
            layout="wide"
        )
        
    def setup_ui(self):
        """Setup the main UI components"""
        st.title("🏥 Pianificazione Turni Infermieri")
        
        # Add configuration to sidebar
        with st.sidebar:
            st.header("Configurazione")
            self.show_configuration_sidebar()
        
        # Create tabs for different sections (now only two)
        tab1, tab2 = st.tabs(["Preferenze e Disponibilità", "Risultati"])
        
        with tab1:
            self.show_preferences_tab()
            
        with tab2:
            self.show_results_tab()
            
        # Display any messages
        if hasattr(self, 'messages') and self.messages:
            self.display_messages(self.messages)
            self.messages = []
    
    def show_configuration_sidebar(self):
        """Show the configuration UI in the sidebar"""
        # Month and year selection
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Italian month names
        italian_months = {
            1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
            5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
            9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
        }
        
        month = st.selectbox(
            "Mese di Pianificazione",
            options=range(1, 13),
            format_func=lambda m: italian_months[m],
            index=current_month - 1,
            key="month_selector"
        )
        
        year = st.number_input(
            "Anno di Pianificazione",
            min_value=current_year,
            max_value=current_year + 5,
            value=current_year,
            key="year_input"
        )
        
        # Calculate days in the month
        days_in_month = calendar.monthrange(year, month)[1]
        st.info(f"Giorni nel mese selezionato: {days_in_month}")
        
        # Number of nurses and freelancers
        num_nurses = st.number_input(
            "Numero di Infermieri",
            min_value=1,
            max_value=10,
            value=3,
            key="num_nurses_input"
        )
        
        num_freelancers = st.number_input(
            "Numero di Liberi Professionisti",
            min_value=0,
            max_value=10,
            value=2,
            key="num_freelancers_input"
        )
        
        # Constraint parameters
        st.subheader("Vincoli")
        
        min_free_weekends = st.number_input(
            "Numero Minimo di Weekend Liberi per Infermiere",
            min_value=0,
            max_value=5,
            value=1,
            key="min_free_weekends_input"
        )
        
        max_consecutive_days = st.slider(
            "Massimo Giorni Consecutivi di Lavoro",
            min_value=1,
            max_value=6,
            value=4,
            key="max_consecutive_days_slider"
        )
        
        max_overhours = st.slider(
            "Massimo Straordinario (turni)",
            min_value=0,
            max_value=5,
            value=1,
            help="Numero massimo di turni straordinari che un infermiere può fare al mese (1 turno = 8 ore)",
            key="max_overhours_slider"
        )
        
        # Work-to-rest ratio slider
        work_rest_ratio = st.slider(
            "Rapporto Lavoro-Riposo",
            min_value=1.0,
            max_value=5.0,
            value=3.0,
            step=0.5,
            help="Rapporto massimo tra giorni di lavoro e giorni di riposo in qualsiasi periodo di 14 giorni. Un valore di 3 significa un massimo di 10-11 giorni di lavoro ogni 14 giorni.",
            key="work_rest_ratio_slider"
        )
        
        # Calculate window days - we don't display this information anymore, but calculate it for reference
        window_size = 14
        max_work_days = min(int(window_size * work_rest_ratio / (1 + work_rest_ratio)), window_size - 1)
        
        st.subheader("Ore Massime per Infermiere")
        
        # Store max nurse hours in session state
        if 'max_nurse_hours' not in st.session_state:
            st.session_state.max_nurse_hours = {i: 160 for i in range(num_nurses)}
        
        # Update session state if number of nurses changes
        if len(st.session_state.max_nurse_hours) != num_nurses:
            st.session_state.max_nurse_hours = {i: 160 for i in range(num_nurses)}
        
        # Display input fields for each nurse's hours
        for i in range(num_nurses):
            st.session_state.max_nurse_hours[i] = st.number_input(
                f"Ore Massime Regolari Infermiere {i+1}",
                min_value=80,
                max_value=200,
                value=st.session_state.max_nurse_hours.get(i, 160),
                key=f"max_nurse_hours_{i}"
            )
        
        # Store configuration in session state
        st.session_state.config = {
            'month': month,
            'year': year,
            'num_nurses': num_nurses,
            'num_freelancers': num_freelancers,
            'min_free_weekends': min_free_weekends,
            'max_consecutive_days': max_consecutive_days,
            'max_nurse_hours': st.session_state.max_nurse_hours,
            'max_overhours': max_overhours,
            'work_rest_ratio': work_rest_ratio
        }
        
        # Track when month/year changes
        current_period = f"{month}_{year}"
        if 'current_period' not in st.session_state:
            st.session_state.current_period = current_period
        elif st.session_state.current_period != current_period:
            # Clear preference and availability data when month/year changes
            if 'nurse_preferences' in st.session_state:
                st.session_state.nurse_preferences = {i: {} for i in range(num_nurses)}
            
            if 'freelancer_availability' in st.session_state:
                st.session_state.freelancer_availability = {i: {} for i in range(num_freelancers)}
            
            # Reset all dataframes
            for key in list(st.session_state.keys()):
                if key.startswith('nurse_') and key.endswith('_pref_df'):
                    del st.session_state[key]
                if key.startswith('freelancer_') and key.endswith('_avail_df'):
                    del st.session_state[key]
                    
            # Update period tracking
            st.session_state.current_period = current_period
    
    def show_preferences_tab(self):
        """Show the preferences tab UI"""
        st.header("Preferenze e Disponibilità")
        
        # Ensure config exists
        if 'config' not in st.session_state:
            st.warning("Configura prima i parametri nella scheda Configurazione.")
            return
        
        # Get configuration
        config = st.session_state.config
        month = config['month']
        year = config['year']
        num_nurses = config['num_nurses']
        num_freelancers = config['num_freelancers']
        
        # Day names translation mapping
        day_mapping = {
            'Monday': 'Lunedì',
            'Tuesday': 'Martedì',
            'Wednesday': 'Mercoledì',
            'Thursday': 'Giovedì',
            'Friday': 'Venerdì',
            'Saturday': 'Sabato',
            'Sunday': 'Domenica'
        }
        
        # Short day names for display
        short_day_names = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
        
        # Generate calendar for the month
        num_days = calendar.monthrange(year, month)[1]
        dates = []
        for day in range(1, num_days + 1):
            date = datetime(year, month, day)
            dates.append({
                'date': date,
                'date_str': date.strftime('%d/%m/%Y'),
                'day_name': day_mapping.get(date.strftime('%A'), date.strftime('%A')),
                'day': day,
                'weekday': date.weekday()  # 0=Monday, 6=Sunday
            })
        
        # Group dates by week
        weeks = []
        current_week = []
        for date_info in dates:
            if date_info['weekday'] == 0 and current_week:  # Monday
                weeks.append(current_week)
                current_week = []
            current_week.append(date_info)
        if current_week:
            weeks.append(current_week)
            
        # Create tabs for nurses and freelancers
        tab_labels = [f"Infermiere {i+1}" for i in range(num_nurses)] + [f"Libero Professionista {i+1}" for i in range(num_freelancers)]
        nurse_tabs = st.tabs(tab_labels)
        
        # Initialize preferences in session state if not already present
        if 'nurse_preferences' not in st.session_state:
            st.session_state.nurse_preferences = {i: {} for i in range(num_nurses)}
        
        if 'freelancer_availability' not in st.session_state:
            st.session_state.freelancer_availability = {i: {} for i in range(num_freelancers)}
        
        # Update the structures if number of nurses/freelancers has changed
        if len(st.session_state.nurse_preferences) != num_nurses:
            st.session_state.nurse_preferences = {
                i: st.session_state.nurse_preferences.get(i, {}) 
                for i in range(num_nurses)
            }
        
        if len(st.session_state.freelancer_availability) != num_freelancers:
            st.session_state.freelancer_availability = {
                i: st.session_state.freelancer_availability.get(i, {}) 
                for i in range(num_freelancers)
            }
        
        # Process nurse preferences
        for nurse_idx in range(num_nurses):
            with nurse_tabs[nurse_idx]:
                # st.subheader(f"Preferenze Infermiere {nurse_idx+1}")
                st.write("Seleziona le preferenze per i turni: spunta le caselle per indicare i turni preferiti")
                
                # Instructions
                st.markdown("""
                - **M**: Turno Mattina
                - **P**: Turno Pomeriggio
                """)
                
                # Display calendar by week
                for week_idx, week in enumerate(weeks):
                    st.write(f"**Settimana {week_idx+1}**")
                    
                    # Create header row with day names
                    cols = st.columns(7)
                    for i, day_name in enumerate(short_day_names):
                        with cols[i]:
                            st.markdown(f"**{day_name}**", help=f"{list(day_mapping.values())[i]}")
                    
                    # Create one row for days
                    cols = st.columns(7)
                    
                    # Fill in empty columns for first week if needed
                    day_slots_used = 0
                    first_day_weekday = week[0]['weekday']
                    for i in range(first_day_weekday):
                        with cols[i]:
                            st.write("")
                        day_slots_used += 1
                    
                    # Display each day
                    for day_info in week:
                        day_num = day_info['day']
                        weekday = day_info['weekday']
                        
                        with cols[weekday]:
                            # Format weekends with different style
                            if weekday >= 5:  # Saturday and Sunday
                                st.markdown(f"<span style='color:red'><b>{day_num}</b></span>", unsafe_allow_html=True)
                            else:
                                st.write(f"**{day_num}**")
                            
                            # Morning preference
                            morning_key = f"nurse_{nurse_idx}_morning_{day_num}_{month}_{year}"
                            morning_pref = (day_num, 'M') in st.session_state.nurse_preferences[nurse_idx]
                            morning = st.checkbox("M", key=morning_key, value=morning_pref)
                            
                            # Afternoon preference
                            afternoon_key = f"nurse_{nurse_idx}_afternoon_{day_num}_{month}_{year}"
                            afternoon_pref = (day_num, 'P') in st.session_state.nurse_preferences[nurse_idx]
                            afternoon = st.checkbox("P", key=afternoon_key, value=afternoon_pref)
                            
                            # Update preferences
                            if morning:
                                st.session_state.nurse_preferences[nurse_idx][(day_num, 'M')] = 1
                            else:
                                st.session_state.nurse_preferences[nurse_idx].pop((day_num, 'M'), None)
                                
                            if afternoon:
                                st.session_state.nurse_preferences[nurse_idx][(day_num, 'P')] = 1
                            else:
                                st.session_state.nurse_preferences[nurse_idx].pop((day_num, 'P'), None)
                        
                        day_slots_used += 1
                    
                    # Fill in empty columns for last week if needed
                    for i in range(day_slots_used, 7):
                        with cols[i]:
                            st.write("")
                    
                    st.write("---")  # Separator between weeks
        
        # Process freelancer availability
        for freelancer_idx in range(num_freelancers):
            with nurse_tabs[num_nurses + freelancer_idx]:
                # st.subheader(f"Disponibilità Libero Professionista {freelancer_idx+1}")
                st.write("Seleziona la disponibilità per i turni: spunta le caselle per indicare disponibilità")
                
                # Instructions
                st.markdown("""
                - **M**: Turno Mattina
                - **P**: Turno Pomeriggio
                """)
                
                # Display calendar by week
                for week_idx, week in enumerate(weeks):
                    st.write(f"**Settimana {week_idx+1}**")
                    
                    # Create header row with day names
                    cols = st.columns(7)
                    for i, day_name in enumerate(short_day_names):
                        with cols[i]:
                            st.markdown(f"**{day_name}**", help=f"{list(day_mapping.values())[i]}")
                    
                    # Create one row for days
                    cols = st.columns(7)
                    
                    # Fill in empty columns for first week if needed
                    day_slots_used = 0
                    first_day_weekday = week[0]['weekday']
                    for i in range(first_day_weekday):
                        with cols[i]:
                            st.write("")
                        day_slots_used += 1
                    
                    # Display each day
                    for day_info in week:
                        day_num = day_info['day']
                        weekday = day_info['weekday']
                        
                        with cols[weekday]:
                            # Format weekends with different style
                            if weekday >= 5:  # Saturday and Sunday
                                st.markdown(f"<span style='color:red'><b>{day_num}</b></span>", unsafe_allow_html=True)
                            else:
                                st.write(f"**{day_num}**")
                            
                            # Morning availability
                            morning_key = f"freelancer_{freelancer_idx}_morning_{day_num}_{month}_{year}"
                            morning_avail = (day_num, 'M') in st.session_state.freelancer_availability[freelancer_idx]
                            morning = st.checkbox("M", key=morning_key, value=morning_avail)
                            
                            # Afternoon availability
                            afternoon_key = f"freelancer_{freelancer_idx}_afternoon_{day_num}_{month}_{year}"
                            afternoon_avail = (day_num, 'P') in st.session_state.freelancer_availability[freelancer_idx]
                            afternoon = st.checkbox("P", key=afternoon_key, value=afternoon_avail)
                            
                            # Update availability
                            if morning:
                                st.session_state.freelancer_availability[freelancer_idx][(day_num, 'M')] = 1
                            else:
                                st.session_state.freelancer_availability[freelancer_idx].pop((day_num, 'M'), None)
                                
                            if afternoon:
                                st.session_state.freelancer_availability[freelancer_idx][(day_num, 'P')] = 1
                            else:
                                st.session_state.freelancer_availability[freelancer_idx].pop((day_num, 'P'), None)
                        
                        day_slots_used += 1
                    
                    # Fill in empty columns for last week if needed
                    for i in range(day_slots_used, 7):
                        with cols[i]:
                            st.write("")
                    
                    st.write("---")  # Separator between weeks
    
    def show_results_tab(self):
        """Show the results tab UI"""
        st.header("Risultati della Pianificazione")
        
        # Check if configuration is completed
        if 'config' not in st.session_state:
            st.warning("Configura prima i parametri nella scheda Configurazione.")
            return
        
        solve_button = st.button("Genera Pianificazione", type="primary", key="solve_button")
        
        if solve_button:
            with st.spinner("Calcolo in corso..."):
                # Instead of just setting a flag, solve the model directly
                from model import SchedulingModel
                
                model = SchedulingModel()
                config = st.session_state.config
                
                try:
                    # Setup the model
                    model.setup_model(
                        year=config['year'],
                        month=config['month'],
                        num_nurses=config['num_nurses'],
                        num_freelancers=config['num_freelancers'],
                        max_nurse_hours=config['max_nurse_hours'],
                        min_free_weekends=config['min_free_weekends'],
                        max_consecutive_days=config['max_consecutive_days'],
                        nurse_preferences=st.session_state.nurse_preferences,
                        freelancer_availability=st.session_state.freelancer_availability,
                        max_overhours=config.get('max_overhours', 1),
                        work_rest_ratio=config.get('work_rest_ratio', 3.0)
                    )
                    
                    # Solve the problem
                    success, schedule_df, hours_worked, free_weekends = model.solve()
                    
                    # Store the result
                    st.session_state.schedule_result = (success, schedule_df, hours_worked, free_weekends)
                    
                    # Force a rerun to show the results
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Errore durante la pianificazione: {str(e)}")
                    st.session_state.schedule_result = (False, None, None, None)
        
        # Display results if available
        if 'schedule_result' in st.session_state and st.session_state.schedule_result[0]:
            success, schedule_df, hours_worked, free_weekends = st.session_state.schedule_result
            
            # Translate day names to Italian
            day_mapping = {
                'Monday': 'Lunedì',
                'Tuesday': 'Martedì',
                'Wednesday': 'Mercoledì',
                'Thursday': 'Giovedì',
                'Friday': 'Venerdì',
                'Saturday': 'Sabato',
                'Sunday': 'Domenica'
            }
            
            schedule_df['Giorno'] = schedule_df['Giorno'].map(lambda x: day_mapping.get(x, x))
            
            # Define shift color scheme
            cell_formatter = {
                "M": "background-color: #ffeb99;",
                "P": "background-color: #99ccff;",
                "M (S)": "background-color: #ffcc99;",
                "P (S)": "background-color: #99ccff; border: 2px solid #ff6666;",
                "R": "background-color: #d9d9d9; color: #777777;"
            }
            
            # Transpose the schedule dataframe - employees as rows, days as columns
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
            
            # Apply styling function to highlight shifts
            def highlight_shifts(row):
                styles = [''] * len(row)
                for i, val in enumerate(row):
                    if i > 0 and isinstance(val, str) and val in cell_formatter:  # Skip the employee column
                        styles[i] = cell_formatter[val]
                return styles
            
            # Style the DataFrame
            styled_df = transposed_df.style.apply(highlight_shifts, axis=1)
            
            # Display the schedule
            st.subheader("Pianificazione Turni")
            
            # Configure columns for display
            column_config = {
                'Dipendente': st.column_config.TextColumn(width="medium")
            }
            
            # Add day columns to configuration
            for col in transposed_df.columns:
                if col != 'Dipendente':
                    column_config[col] = st.column_config.TextColumn(width="small")
            
            st.dataframe(
                transposed_df,
                column_config=column_config,
                hide_index=True,
                key="results_dataframe",
                height=min(600, 100 + (len(employees) + 1) * 35)  # Adjust height based on number of rows
            )
            
            # Create and display summary table
            st.subheader("Riepilogo per Infermiere")
            
            # Create summary data
            summary_data = []
            config = st.session_state.config
            
            for nurse_id in range(config['num_nurses']):
                max_hours = config['max_nurse_hours'][nurse_id]
                total_hours = hours_worked[nurse_id] if nurse_id in hours_worked else 0
                overtime_hours = hours_worked.get(f'{nurse_id}_overtime', 0)
                target_weekends = config['min_free_weekends']
                actual_weekends = free_weekends[nurse_id] if nurse_id in free_weekends else 0
                max_ot_shifts = config.get('max_overhours', 1)
                max_ot_hours = max_ot_shifts * 8
                
                summary_data.append({
                    'Infermiere': f"Infermiere {nurse_id + 1}",
                    'Ore Target': max_hours,
                    'Ore Straordinario': overtime_hours,
                    'Ore Lavorate': total_hours,
                    'Straordinario OK': overtime_hours <= max_ot_hours,
                    'Weekend Liberi': actual_weekends,
                    'Weekends Minimi': target_weekends,
                    'Weekends OK': actual_weekends >= target_weekends
                })
            
            summary_df = pd.DataFrame(summary_data)
            
            # Display summary table
            st.dataframe(
                summary_df,
                column_config={
                    'Infermiere': st.column_config.TextColumn(width="medium"),
                    'Ore Target': st.column_config.NumberColumn(format="%d ore", width="small"),
                    'Ore Straordinario': st.column_config.NumberColumn(format="%d ore", width="small"),
                    'Ore Lavorate': st.column_config.NumberColumn(format="%d ore", width="small"),
                    'Straordinario OK': st.column_config.CheckboxColumn(
                        help=f"Indica se le ore straordinarie sono entro il limite specificato ({max_ot_shifts} turni = {max_ot_hours} ore)"
                    ),
                    'Weekend Liberi': st.column_config.NumberColumn(width="small"),
                    'Weekends Minimi': st.column_config.NumberColumn(width="small"),
                    'Weekends OK': st.column_config.CheckboxColumn(
                        help="Indica se il numero di weekend liberi soddisfa il requisito minimo"
                    )
                },
                hide_index=True,
                key="summary_dataframe"
            )
            
            # Create and display freelancers summary table
            if config['num_freelancers'] > 0:
                st.subheader("Riepilogo per Liberi Professionisti")
                
                # Create summary data for freelancers
                freelancer_summary_data = []
                
                # Calculate total hours and shifts for each freelancer
                for f_idx in range(config['num_freelancers']):
                    # Calculate freelancer ID - though not needed, we'll keep for clarity
                    freelancer_id = config['num_nurses'] + f_idx
                    
                    total_shifts = 0
                    total_hours = 0
                    morning_shifts = 0
                    afternoon_shifts = 0
                    
                    # Count shifts
                    for d in range(len(schedule_df)):
                        freelancer_col = f"Libero Professionista {f_idx+1}"
                        if freelancer_col in schedule_df.columns:
                            shift_value = schedule_df.iloc[d][freelancer_col]
                            if shift_value == "M":
                                total_shifts += 1
                                morning_shifts += 1
                                total_hours += 8  # Assuming 8 hours per shift
                            elif shift_value == "P":
                                total_shifts += 1
                                afternoon_shifts += 1
                                total_hours += 8  # Assuming 8 hours per shift
                    
                    # Calculate availability usage
                    available_slots = 0
                    if f_idx in st.session_state.freelancer_availability:
                        available_slots = len(st.session_state.freelancer_availability[f_idx])
                    
                    availability_usage = 0
                    if available_slots > 0:
                        availability_usage = round((total_shifts / available_slots) * 100, 1)
                    
                    # Add to summary
                    freelancer_summary_data.append({
                        'Libero Professionista': f"Libero Professionista {f_idx + 1}",
                        'Turni Totali': total_shifts,
                        'Turni Mattina': morning_shifts,
                        'Turni Pomeriggio': afternoon_shifts,
                        'Ore Totali': total_hours,
                        'Disponibilità Usata (%)': availability_usage
                    })
                
                freelancer_summary_df = pd.DataFrame(freelancer_summary_data)
                
                # Display freelancer summary table
                st.dataframe(
                    freelancer_summary_df,
                    column_config={
                        'Libero Professionista': st.column_config.TextColumn(width="medium"),
                        'Turni Totali': st.column_config.NumberColumn(width="small"),
                        'Turni Mattina': st.column_config.NumberColumn(width="small"),
                        'Turni Pomeriggio': st.column_config.NumberColumn(width="small"),
                        'Ore Totali': st.column_config.NumberColumn(format="%d ore", width="small"),
                        'Disponibilità Usata (%)': st.column_config.NumberColumn(
                            format="%.1f%%",
                            help="Percentuale di turni assegnati rispetto alla disponibilità indicata"
                        )
                    },
                    hide_index=True,
                    key="freelancer_summary_dataframe"
                )
            
            # Export options
            # st.subheader("Esporta Pianificazione")
            
            # Create Excel download button that generates and downloads in one step
            if 'schedule_result' in st.session_state and st.session_state.schedule_result[0]:
                _, curr_schedule_df, hours_worked, free_weekends = st.session_state.schedule_result
                config = st.session_state.config
                
                # Generate filename for download
                filename = f"turni_{config['month']}_{config['year']}.xlsx"
                
                # Generate Excel file data
                excel_data = None
                with st.spinner("Preparazione file Excel..."):
                    try:
                        # Create model instance for export
                        from model import SchedulingModel
                        model = SchedulingModel()
                        
                        # Export to Excel in-memory
                        excel_data = model.export_to_excel_bytes(
                            curr_schedule_df,
                            filename,
                            hours_worked=hours_worked,
                            nurse_hours=config['max_nurse_hours'],
                            hours_flexibility=config.get('max_overhours', 1) * 8,
                            free_weekends=free_weekends,
                            min_free_weekends=config.get('min_free_weekends', 1)
                        )
                    except Exception as e:
                        st.error(f"Errore durante l'esportazione: {str(e)}")
                
                # Create download button with the generated Excel data
                if excel_data:
                    st.download_button(
                        label="Esporta in Excel",
                        data=excel_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="excel_download",
                        use_container_width=True
                    )
        
        elif 'schedule_result' in st.session_state and not st.session_state.schedule_result[0]:
            st.error("Impossibile trovare una soluzione valida con i vincoli specificati. Prova a modificare i parametri.")
    
    def show_excel_download(self, excel_data, filename):
        """Display download button for Excel file"""
        st.download_button(
            label="Download Excel File",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_download"
        )
        
    def display_messages(self, messages):
        """Display messages to the user"""
        for msg_type, msg in messages:
            if msg_type == "info":
                st.info(msg)
            elif msg_type == "success":
                st.success(msg)
            elif msg_type == "warning":
                st.warning(msg)
            elif msg_type == "error":
                st.error(msg)
