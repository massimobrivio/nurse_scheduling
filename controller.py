import streamlit as st
import io
from model import SchedulingModel
from view import SchedulingView

class SchedulingController:
    def __init__(self):
        self.model = SchedulingModel()
        self.view = SchedulingView()
        self.messages = []
    
    def run(self):
        """Run the application"""
        # Process actions before rendering UI
        # Check if a solve is requested
        if 'solve_requested' in st.session_state and st.session_state.solve_requested:
            self.solve_scheduling()
            # Reset flag
            st.session_state.solve_requested = False
        
        # Check if Excel export is requested
        if 'export_excel_requested' in st.session_state and st.session_state.export_excel_requested and 'schedule_result' in st.session_state:
            self.export_excel()
            # Reset flag
            st.session_state.export_excel_requested = False
            
        # Pass messages to view
        self.view.messages = self.messages
        
        # Setup the UI
        self.view.setup_ui()
        
        # Clear messages after displaying
        self.messages = []
    
    def solve_scheduling(self):
        """Solve the scheduling problem"""
        if 'config' not in st.session_state:
            self.messages.append(("error", "Configurazione mancante."))
            return
        
        config = st.session_state.config
        
        # Setup the model
        try:
            self.model.setup_model(
                year=config['year'],
                month=config['month'],
                num_nurses=config['num_nurses'],
                num_freelancers=config['num_freelancers'],
                nurse_hours=config['nurse_hours'],
                min_free_weekends=config['min_free_weekends'],
                max_consecutive_days=config['max_consecutive_days'],
                nurse_preferences=st.session_state.nurse_preferences,
                freelancer_availability=st.session_state.freelancer_availability,
                hours_flexibility=config.get('hours_flexibility', 8)
            )
            
            # Solve the problem
            success, schedule_df, hours_worked, free_weekends = self.model.solve()
            
            # Store the result
            st.session_state.schedule_result = (success, schedule_df, hours_worked, free_weekends)
            
            if success:
                self.messages.append(("success", "Pianificazione generata con successo!"))
            else:
                self.messages.append(("error", "Non è stato possibile trovare una soluzione. Prova a modificare i vincoli."))
        
        except Exception as e:
            self.messages.append(("error", f"Errore durante la pianificazione: {str(e)}"))
            st.session_state.schedule_result = (False, None, None, None)
    
    def export_excel(self):
        """Export the schedule to Excel"""
        if 'schedule_result' not in st.session_state or not st.session_state.schedule_result[0]:
            self.messages.append(("error", "Nessuna pianificazione disponibile da esportare."))
            return
        
        try:
            _, schedule_df, hours_worked, free_weekends = st.session_state.schedule_result
            
            # Translate day names to Italian if not already done
            day_mapping = {
                'Monday': 'Lunedì',
                'Tuesday': 'Martedì',
                'Wednesday': 'Mercoledì',
                'Thursday': 'Giovedì',
                'Friday': 'Venerdì',
                'Saturday': 'Sabato',
                'Sunday': 'Domenica'
            }
            
            if schedule_df['Giorno'].iloc[0] in day_mapping:
                schedule_df['Giorno'] = schedule_df['Giorno'].map(lambda x: day_mapping.get(x, x))
            
            # Get configuration
            config = st.session_state.config
            
            # Export to Excel
            filename = f"turni_{config['month']}_{config['year']}.xlsx"
            self.model.export_to_excel(
                schedule_df, 
                filename, 
                hours_worked=hours_worked, 
                nurse_hours=config['nurse_hours'],
                hours_flexibility=config.get('hours_flexibility', 8),
                free_weekends=free_weekends,
                min_free_weekends=config.get('min_free_weekends', 1)
            )
            
            # Add success message
            self.messages.append(("success", f"Excel file '{filename}' creato con successo."))
            
            # Instruct user to download from their file system
            self.messages.append(("info", f"Il file è stato salvato nella cartella corrente: {filename}"))
        
        except Exception as e:
            self.messages.append(("error", f"Errore durante l'esportazione: {str(e)}"))

# Entry point for the Streamlit app
def main():
    controller = SchedulingController()
    controller.run()

if __name__ == "__main__":
    main()
