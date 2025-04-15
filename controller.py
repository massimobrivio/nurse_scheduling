import streamlit as st
from model import NurseSchedulingModel
from view import NurseSchedulingView
import calendar
from datetime import datetime, timedelta
import pandas as pd

class NurseSchedulingController:
    def __init__(self):
        """Inizializza il controller con il modello e la vista"""
        self.model = NurseSchedulingModel()
        self.view = NurseSchedulingView()
        
        # Inizializza lo stato dell'applicazione
        if 'schedule_result' not in st.session_state:
            st.session_state.schedule_result = None
        if 'schedule_df' not in st.session_state:
            st.session_state.schedule_df = None
    
    def run(self):
        """Esegue l'applicazione principale"""
        # Ottiene il layout della vista
        ui = self.view.main_layout()
        
        # Ottiene i parametri dall'interfaccia
        params = ui["params"]
        tabs = ui["tabs"]
        
        # Aggiorna il numero di infermieri nel modello
        self.model.num_nurses = params["num_nurses"]
        
        # Calcola date di inizio e fine dal mese e anno selezionati
        if params.get("use_date_range", False):
            # Usa il range di date direttamente
            date_start = params["date_start"]
            date_end = params["date_end"]
        else:
            # Usa anno e mese per calcolare l'intero mese
            year = params["year"]
            month = params["month"]
            _, last_day = calendar.monthrange(year, month)
            date_start = datetime(year, month, 1).date()
            date_end = datetime(year, month, last_day).date()
        
        # Gestisce le preferenze degli infermieri
        preferences = self.view.show_preferences_input(
            tabs[2], 
            params["num_nurses"], 
            date_start,
            date_end
        )
        
        # Se il pulsante per generare la pianificazione è stato premuto
        if params["generate"]:
            # Esegui il modello per generare la pianificazione
            result = self.model.solve_schedule(
                date_start=date_start,
                date_end=date_end,
                min_free_weekends=params["min_free_weekends"],
                max_consecutive_days=params["max_consecutive_days"],
                nurse_preferences=preferences
            )
            
            # Salva il risultato nello stato della sessione
            st.session_state.schedule_result = result
            
            if result["status"] in ["ottimale", "fattibile"]:
                # Converti il dizionario di pianificazione in un DataFrame
                schedule_df = self.model.get_schedule_dataframe(result["schedule"])
                st.session_state.schedule_df = schedule_df
                
                # Mostra un messaggio di successo
                self.view.show_message(
                    f"Pianificazione generata con successo! Stato: {result['status']}", 
                    "success"
                )
            else:
                # Mostra un messaggio di errore
                self.view.show_message(
                    "Impossibile trovare una pianificazione valida con i vincoli specificati.",
                    "error"
                )
        
        # Mostra la pianificazione nella tab appropriata
        hours_worked = None
        parameters = None
        preferences_data = None
        objective_data = None
        hour_deviations = None
        if st.session_state.schedule_result:
            if 'hours_worked' in st.session_state.schedule_result:
                hours_worked = st.session_state.schedule_result["hours_worked"]
            if 'parameters' in st.session_state.schedule_result:
                parameters = st.session_state.schedule_result["parameters"]
            if 'preferences' in st.session_state.schedule_result:
                preferences_data = st.session_state.schedule_result["preferences"]
            if 'objective' in st.session_state.schedule_result:
                objective_data = st.session_state.schedule_result["objective"]
            if 'hour_deviations' in st.session_state.schedule_result:
                hour_deviations = st.session_state.schedule_result["hour_deviations"]
                
        self.view.show_schedule(
            tabs[0], 
            st.session_state.schedule_df,
            hours_worked,
            None,  # No statistics
            parameters,
            preferences_data,
            objective_data,
            hour_deviations
        )
        
        # Mostra l'analisi nella tab appropriata
        self.view.show_analysis(tabs[1], st.session_state.schedule_df)
        
        # Se esiste una pianificazione, mostra i pulsanti per scaricarla
        if st.session_state.schedule_df is not None:
            if params.get("use_date_range", False):
                filename = f"pianificazione_infermieri_{date_start.strftime('%Y-%m-%d')}_{date_end.strftime('%Y-%m-%d')}"
            else:
                month_name = calendar.month_name[params["month"]]
                filename = f"pianificazione_infermieri_{params['year']}_{month_name}"
                
            self.view.download_button(
                st.session_state.schedule_df,
                filename
            )

# Funzione principale per eseguire l'applicazione
def main():
    controller = NurseSchedulingController()
    controller.run()

if __name__ == "__main__":
    main()
