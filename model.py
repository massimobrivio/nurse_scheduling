from ortools.sat.python import cp_model
import pandas as pd
import calendar
from datetime import datetime, timedelta
import numpy as np

class NurseSchedulingModel:
    def __init__(self):
        # Dati predefiniti
        self.num_nurses = 3
        self.num_shifts = 2  # Mattino (M): 6:00-14:00, Pomeriggio (P): 14:00-22:00
        self.shift_duration = 8  # ore
        self.monthly_contracted_hours = 165  # Ore mensili contrattuali
        self.max_hour_deviation = 8  # Deviazione massima consentita dalle ore contrattuali (±8 ore)
        self.preferences = {}  # Preferenze delle infermiere

    def generate_calendar(self, date_start, date_end):
        """Genera un calendario per il periodo specificato"""
        if isinstance(date_start, str):
            date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        if isinstance(date_end, str):
            date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
            
        num_days = (date_end - date_start).days + 1
        dates = [(date_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]
        return dates, num_days

    def solve_schedule(self, date_start, date_end, min_free_weekends=2, max_consecutive_days=6, nurse_preferences=None):
        """Risolve il problema di pianificazione per il periodo specificato
        
        Args:
            date_start: Data di inizio pianificazione (formato YYYY-MM-DD o oggetto datetime.date)
            date_end: Data di fine pianificazione (formato YYYY-MM-DD o oggetto datetime.date)
            min_free_weekends: Numero minimo di weekend liberi per ogni infermiere
            max_consecutive_days: Numero massimo di giorni consecutivi di lavoro
            nurse_preferences: Dizionario di preferenze delle infermiere
        """
        # Converti le date in oggetti datetime se sono stringhe
        if isinstance(date_start, str):
            date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        if isinstance(date_end, str):
            date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
            
        dates, num_days = self.generate_calendar(date_start, date_end)
        all_nurses = range(self.num_nurses)
        all_shifts = range(self.num_shifts)
        all_days = range(num_days)
        
        # Calcola le ore contrattuali pro-rata per il periodo di pianificazione
        # (es. se pianifichiamo 15 giorni su un mese di 30, le ore contrattuali sarebbero 165/2 = 82.5)
        days_in_month = calendar.monthrange(date_start.year, date_start.month)[1]
        if date_start.month == date_end.month and date_start.year == date_end.year:
            # Stesso mese
            period_ratio = num_days / days_in_month
        else:
            # Periodo su più mesi, usiamo 30 giorni come approssimazione
            period_ratio = num_days / 30
        
        target_hours = round(self.monthly_contracted_hours * period_ratio)
        min_hours = max(0, target_hours - self.max_hour_deviation)
        max_hours = target_hours + self.max_hour_deviation
        
        # Crea il modello
        model = cp_model.CpModel()
        
        # Crea le variabili
        shifts = {}
        for n in all_nurses:
            for d in all_days:
                for s in all_shifts:
                    shifts[(n, d, s)] = model.new_bool_var(f"shift_n{n}_d{d}_s{s}")
        
        # Ogni turno è assegnato esattamente a un'infermiera
        for d in all_days:
            for s in all_shifts:
                model.add_exactly_one(shifts[(n, d, s)] for n in all_nurses)
        
        # Ogni infermiera lavora al massimo un turno al giorno
        for n in all_nurses:
            for d in all_days:
                model.add_at_most_one(shifts[(n, d, s)] for s in all_shifts)
        
        # Calcola il numero di turni e ore per ogni infermiera
        nurse_shifts = []
        nurse_hours = []
        hours_deviation = []
        
        for n in all_nurses:
            shifts_worked = []
            for d in all_days:
                for s in all_shifts:
                    shifts_worked.append(shifts[(n, d, s)])
            
            # Crea una variabile per il numero totale di turni lavorati da ogni infermiera
            total_shifts = len(all_days) * len(all_shifts)
            nurse_total_shifts = model.new_int_var(0, total_shifts, f"nurse_{n}_total_shifts")
            model.add(nurse_total_shifts == sum(shifts_worked))
            nurse_shifts.append(nurse_total_shifts)
            
            # Calcola le ore totali lavorate
            nurse_total_hours = model.new_int_var(min_hours, max_hours, f"nurse_{n}_total_hours")
            model.add(nurse_total_hours == nurse_total_shifts * self.shift_duration)
            nurse_hours.append(nurse_total_hours)
            
            # Calcola la deviazione dalle ore target
            deviation_pos = model.new_int_var(0, self.max_hour_deviation, f"nurse_{n}_deviation_pos")
            deviation_neg = model.new_int_var(0, self.max_hour_deviation, f"nurse_{n}_deviation_neg")
            
            model.add(nurse_total_hours == target_hours + deviation_pos - deviation_neg)
            hours_deviation.append(deviation_pos + deviation_neg)
        
        # Distribuisci equamente i turni tra le infermiere
        for i in range(len(all_nurses)):
            for j in range(i + 1, len(all_nurses)):
                # La differenza nel numero di turni tra due infermiere è al massimo 1
                model.add((nurse_shifts[i] - nurse_shifts[j]) <= 1)
                model.add((nurse_shifts[j] - nurse_shifts[i]) <= 1)
        
        # Vincolo: massimo max_consecutive_days giorni consecutivi di lavoro
        for n in all_nurses:
            for d in range(num_days - max_consecutive_days):
                # Somma dei turni per (max_consecutive_days + 1) giorni consecutivi
                consecutive_days = []
                for i in range(max_consecutive_days + 1):
                    for s in all_shifts:
                        consecutive_days.append(shifts[(n, d + i, s)])
                # Al massimo max_consecutive_days turni in (max_consecutive_days + 1) giorni consecutivi
                model.add(sum(consecutive_days) <= max_consecutive_days)
        
        # Vincolo: non si può passare da turno pomeriggio a turno mattina il giorno dopo
        for n in all_nurses:
            for d in range(num_days - 1):
                # Se lavora nel turno pomeriggio (1), non può lavorare nel turno mattina (0) il giorno dopo
                model.add(shifts[(n, d, 1)] + shifts[(n, d + 1, 0)] <= 1)
        
        # Vincolo: almeno min_free_weekends weekend liberi nel periodo
        weekend_days = []
        for d in range(num_days):
            current_date = date_start + timedelta(days=d)
            day_of_week = current_date.weekday()
            if day_of_week == 5 or day_of_week == 6:  # Sabato o Domenica
                weekend_days.append(d)
        
        # Raggruppa i weekend
        weekends = []
        current_weekend = []
        for d in weekend_days:
            if not current_weekend or d == current_weekend[-1] + 1:
                current_weekend.append(d)
            else:
                weekends.append(current_weekend)
                current_weekend = [d]
        if current_weekend:
            weekends.append(current_weekend)
        
        # Per ogni infermiera, crea variabili per i weekend liberi
        free_weekends = {}
        for n in all_nurses:
            for i, weekend in enumerate(weekends):
                # Un weekend è libero se l'infermiera non lavora in nessun giorno del weekend
                weekend_shifts = []
                for d in weekend:
                    for s in all_shifts:
                        weekend_shifts.append(shifts[(n, d, s)])
                
                # Il weekend è libero se non ci sono turni
                free_weekends[(n, i)] = model.new_bool_var(f"free_weekend_n{n}_w{i}")
                
                # Correct implementation using the proper pattern:
                model.add(sum(weekend_shifts) == 0).only_enforce_if(free_weekends[(n, i)])
                model.add(sum(weekend_shifts) >= 1).only_enforce_if(~free_weekends[(n, i)])
            
            # Ogni infermiera deve avere almeno min_free_weekends weekend liberi
            # Verificare che ci siano abbastanza weekend nel periodo
            num_required = min(min_free_weekends, len(weekends))
            if num_required > 0:
                model.add(sum(free_weekends[(n, i)] for i in range(len(weekends))) >= num_required)
        
        # Variabili per le preferenze soddisfatte
        preference_variables = {}
        total_preferences = 0
        
        # Imposta l'obiettivo del modello
        objective_description = ""
        objective_terms = []
        
        # Aggiungi i termini per le deviazioni dalle ore target
        for dev in hours_deviation:
            objective_terms.append(dev)
        
        # Se ci sono preferenze delle infermiere, aggiungi l'obiettivo di massimizzarle
        if nurse_preferences and len(nurse_preferences) > 0:
            preference_met = []
            total_preferences = len(nurse_preferences)
            
            for n in all_nurses:
                for d in all_days:
                    for s in all_shifts:
                        if (n, d, s) in nurse_preferences and nurse_preferences[(n, d, s)] == 1:
                            # Crea una variabile per ogni preferenza
                            pref_var = model.new_bool_var(f"pref_n{n}_d{d}_s{s}")
                            preference_variables[(n, d, s)] = pref_var
                            
                            # La variabile è vera se la preferenza è soddisfatta
                            model.add(pref_var == shifts[(n, d, s)])
                            
                            # Aggiungi la variabile all'obiettivo (con peso più alto per dare priorità)
                            preference_met.append(10 * pref_var)  # Peso 10 volte maggiore delle deviazioni orarie
                            objective_terms.append(10 * pref_var)
            
            objective_description = "Massimizzazione delle preferenze e minimizzazione delle deviazioni orarie"
            model.maximize(sum(objective_terms))
        else:
            # Obiettivo predefinito: minimizzare le deviazioni dalle ore target
            objective_description = "Minimizzazione delle deviazioni dalle ore contrattuali"
            model.minimize(sum(objective_terms))
        
        # Risolutore
        solver = cp_model.CpSolver()
        status = solver.solve(model)
        
        # Prepara il risultato
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            schedule = {}
            for d in all_days:
                date = dates[d]
                schedule[date] = {}
                for n in all_nurses:
                    schedule[date][f"Infermiere {n+1}"] = "Riposo"
                    for s in all_shifts:
                        if solver.value(shifts[(n, d, s)]) == 1:
                            shift_name = "Mattino" if s == 0 else "Pomeriggio"
                            schedule[date][f"Infermiere {n+1}"] = shift_name
            
            # Calcola le ore lavorate per ogni infermiera
            hours_worked = {f"Infermiere {n+1}": 0 for n in all_nurses}
            shifts_worked = {f"Infermiere {n+1}": 0 for n in all_nurses}
            
            for d in all_days:
                for n in all_nurses:
                    for s in all_shifts:
                        if solver.value(shifts[(n, d, s)]) == 1:
                            hours_worked[f"Infermiere {n+1}"] += self.shift_duration
                            shifts_worked[f"Infermiere {n+1}"] += 1
            
            # Calcola le preferenze soddisfatte
            preferences_met = 0
            preferences_details = {}
            
            if nurse_preferences and total_preferences > 0:
                for (n, d, s), pref_var in preference_variables.items():
                    if solver.value(pref_var) == 1:
                        preferences_met += 1
                        nurse_name = f"Infermiere {n+1}"
                        shift_name = "Mattino" if s == 0 else "Pomeriggio"
                        date_str = dates[d]
                        
                        if nurse_name not in preferences_details:
                            preferences_details[nurse_name] = []
                            
                        preferences_details[nurse_name].append({
                            "data": date_str,
                            "turno": shift_name
                        })
                
                preferences_percentage = (preferences_met / total_preferences) * 100
            else:
                preferences_percentage = 0
            
            # Calcola la differenza massima nei turni lavorati
            min_worked = min(shifts_worked.values())
            max_worked = max(shifts_worked.values())
            shift_difference = max_worked - min_worked
            
            # Calcola le deviazioni dalle ore contrattuali
            hour_deviations = {}
            for n in all_nurses:
                nurse_name = f"Infermiere {n+1}"
                worked = hours_worked[nurse_name]
                deviation = worked - target_hours
                hour_deviations[nurse_name] = deviation
            
            return {
                "status": "ottimale" if status == cp_model.OPTIMAL else "fattibile",
                "schedule": schedule,
                "hours_worked": hours_worked,
                "shifts_worked": shifts_worked,
                "parameters": {
                    "date_start": date_start.strftime("%Y-%m-%d"),
                    "date_end": date_end.strftime("%Y-%m-%d"),
                    "min_free_weekends": min_free_weekends,
                    "max_consecutive_days": max_consecutive_days,
                    "target_hours": target_hours,
                    "min_hours": min_hours,
                    "max_hours": max_hours
                },
                "objective": {
                    "description": objective_description,
                    "shift_difference": shift_difference
                },
                "hour_deviations": hour_deviations,
                "preferences": {
                    "total": total_preferences,
                    "met": preferences_met,
                    "percentage": preferences_percentage,
                    "details": preferences_details
                },
                "statistics": {
                    "conflicts": solver.num_conflicts,
                    "branches": solver.num_branches,
                    "wall_time": solver.wall_time
                }
            }
        else:
            return {
                "status": "non fattibile",
                "schedule": None,
                "parameters": {
                    "date_start": date_start.strftime("%Y-%m-%d"),
                    "date_end": date_end.strftime("%Y-%m-%d"),
                    "min_free_weekends": min_free_weekends,
                    "max_consecutive_days": max_consecutive_days,
                    "target_hours": target_hours,
                    "min_hours": min_hours,
                    "max_hours": max_hours
                },
                "objective": {
                    "description": objective_description
                },
                "preferences": {
                    "total": total_preferences,
                    "met": 0,
                    "percentage": 0,
                    "details": {}
                },
                "statistics": {
                    "conflicts": solver.num_conflicts,
                    "branches": solver.num_branches,
                    "wall_time": solver.wall_time
                }
            }
    
    def get_schedule_dataframe(self, schedule):
        """Converte il dizionario di pianificazione in un DataFrame pandas"""
        if not schedule:
            return None
        
        dates = sorted(schedule.keys())
        df_data = []
        
        for date in dates:
            row_data = {"Data": date}
            for nurse, shift in schedule[date].items():
                row_data[nurse] = shift
            df_data.append(row_data)
        
        df = pd.DataFrame(df_data)
        return df
