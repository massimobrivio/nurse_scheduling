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
                hours_flexibility=config.get('hours_flexibility', 8),
                work_rest_ratio=config.get('work_rest_ratio', 3.0)
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

# Entry point for the Streamlit app
def main():
    controller = SchedulingController()
    controller.run()

if __name__ == "__main__":
    main()
