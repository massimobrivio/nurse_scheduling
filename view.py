import streamlit as st
import pandas as pd
import numpy as np
import datetime
import calendar
import plotly.express as px
import io

class NurseSchedulingView:
    def __init__(self):
        # Impostazioni pagina
        st.set_page_config(
            page_title="Pianificazione Turni Infermieri",
            page_icon="👩‍⚕️",
            layout="wide"
        )
        
    def main_layout(self):
        """Layout principale dell'applicazione"""
        st.title("👩‍⚕️ Sistema di Pianificazione Turni Infermieri")
        st.markdown("---")
        
        # Sidebar per i parametri di input
        with st.sidebar:
            st.header("Parametri")
            num_nurses = st.number_input("Numero di Infermieri", min_value=1, max_value=10, value=3)
            st.markdown("---")
            
            st.header("Configurazione Pianificazione")
            
            # Toggle tra selezione mese e range di date
            use_date_range = st.checkbox("Usa range di date personalizzato", value=False)
            
            current_year = datetime.datetime.now().year
            current_month = datetime.datetime.now().month
            
            # Date di inizio e fine pianificazione
            if use_date_range:
                # Usa range di date personalizzato
                today = datetime.date.today()
                date_start = st.date_input("Data inizio", today)
                date_end = st.date_input("Data fine", today + datetime.timedelta(days=30))
                
                # Verifica che la data di fine sia successiva alla data di inizio
                if date_end < date_start:
                    st.warning("La data di fine deve essere successiva alla data di inizio.")
                    date_end = date_start
                    
                # Resetta le preferenze quando cambia l'intervallo di date
                if 'last_date_range' not in st.session_state or st.session_state.last_date_range != (date_start, date_end):
                    if 'preferences_df' in st.session_state:
                        del st.session_state.preferences_df
                    st.session_state.last_date_range = (date_start, date_end)
            else:
                # Usa anno e mese
                year = st.selectbox("Anno", options=range(current_year, current_year + 2), index=0)
                month = st.selectbox("Mese", options=range(1, 13), index=current_month - 1, 
                                  format_func=lambda m: calendar.month_name[m])
                
                # Resetta le preferenze quando cambia mese/anno
                if 'last_month_year' not in st.session_state or st.session_state.last_month_year != (year, month):
                    if 'preferences_df' in st.session_state:
                        del st.session_state.preferences_df
                    st.session_state.last_month_year = (year, month)
            
            st.markdown("---")
            st.header("Vincoli")
            
            # Parametri per i vincoli
            min_free_weekends = st.number_input("Numero minimo di weekend liberi", 
                                              min_value=0, max_value=5, value=2)
            max_consecutive_days = st.number_input("Massimo giorni consecutivi di lavoro", 
                                               min_value=1, max_value=10, value=6)
            
            st.markdown("---")
            generate_button = st.button("Genera Pianificazione", type="primary")
        
        # Tabs per visualizzare diverse sezioni
        tabs = st.tabs(["Pianificazione", "Analisi", "Preferenze"])
        
        # Costruisci il dizionario dei parametri
        params = {
            "num_nurses": num_nurses,
            "use_date_range": use_date_range,
            "min_free_weekends": min_free_weekends,
            "max_consecutive_days": max_consecutive_days,
            "generate": generate_button
        }
        
        # Aggiungi i parametri specifici in base al tipo di pianificazione
        if use_date_range:
            params["date_start"] = date_start
            params["date_end"] = date_end
        else:
            params["year"] = year
            params["month"] = month
        
        return {
            "tabs": tabs,
            "params": params
        }
        
    def show_schedule(self, tab, schedule_df, hours_worked=None, statistics=None, parameters=None, preferences=None, objective=None, hour_deviations=None):
        """Mostra la pianificazione nella tab pianificazione"""
        with tab:
            if schedule_df is not None:
                st.subheader("📅 Pianificazione Mensile")
                st.dataframe(schedule_df, use_container_width=True)
                
                # Mostra i parametri della pianificazione
                if parameters:
                    st.subheader("⚙️ Parametri di Pianificazione")
                    params_col1, params_col2 = st.columns(2)
                    
                    with params_col1:
                        st.markdown(f"""
                        - **Periodo**: dal {parameters.get('date_start')} al {parameters.get('date_end')}
                        - **Weekend liberi minimi**: {parameters.get('min_free_weekends')}
                        """)
                        
                    with params_col2:
                        st.markdown(f"""
                        - **Giorni consecutivi max**: {parameters.get('max_consecutive_days')}
                        - **Numero infermieri**: {len(schedule_df.columns) - 1}
                        """)
                    
                    # Aggiungi le informazioni sulle ore contrattuali
                    if 'target_hours' in parameters:
                        st.markdown(f"""
                        - **Ore contrattuali periodo**: {parameters.get('target_hours')} (range ammesso: {parameters.get('min_hours')}-{parameters.get('max_hours')})
                        """)
                
                # Mostra l'obiettivo ottimizzato
                if objective:
                    st.subheader("🎯 Obiettivo Ottimizzato")
                    description = objective.get('description', '')
                    st.write(description)
                    
                    # Se l'obiettivo è l'equità nella distribuzione dei turni, mostra la differenza
                    if "equità" in description.lower() and 'shift_difference' in objective:
                        shift_difference = objective.get('shift_difference', 0)
                        if shift_difference == 0:
                            st.success(f"🌟 Distribuzione perfettamente equa! Tutti gli infermieri hanno lo stesso numero di turni.")
                        else:
                            st.info(f"📊 Differenza massima nel numero di turni: {shift_difference} turni")
                
                # Mostra informazioni sulle preferenze soddisfatte
                if preferences:
                    st.subheader("🔍 Preferenze Soddisfatte")
                    total = preferences.get('total', 0)
                    met = preferences.get('met', 0)
                    percentage = preferences.get('percentage', 0)
                    
                    if total > 0:
                        # Crea un grafico del progresso con la percentuale di preferenze soddisfatte
                        st.progress(percentage / 100, f"Preferenze soddisfatte: {percentage:.1f}% ({met}/{total})")
                        
                        # Mostra i dettagli delle preferenze soddisfatte per infermiere
                        details = preferences.get('details', {})
                        if details:
                            st.subheader("Dettaglio Preferenze Soddisfatte")
                            for nurse, prefs in details.items():
                                with st.expander(f"{nurse} - {len(prefs)} preferenze soddisfatte"):
                                    prefs_df = pd.DataFrame(prefs)
                                    st.dataframe(prefs_df, use_container_width=True)
                    else:
                        st.info("Nessuna preferenza specificata per questa pianificazione.")
                
                if hours_worked:
                    st.subheader("⏱️ Ore Lavorate")
                    
                    if hour_deviations and parameters and 'target_hours' in parameters:
                        target_hours = parameters.get('target_hours', 0)
                        
                        # Crea un DataFrame con ore lavorate e deviazioni
                        hours_df = pd.DataFrame({
                            "Infermiere": list(hours_worked.keys()),
                            "Ore Lavorate": list(hours_worked.values()),
                            "Ore Target": [target_hours] * len(hours_worked),
                            "Deviazione": [hour_deviations.get(nurse, 0) for nurse in hours_worked.keys()]
                        })
                        
                        # Formatta le deviazioni con segno + o -
                        hours_df["Credito/Debito"] = hours_df["Deviazione"].apply(
                            lambda x: f"+{x}" if x > 0 else str(x)
                        )
                        
                        # Crea due colonne
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            # Mostra il DataFrame con le informazioni sulle ore
                            display_df = hours_df[["Infermiere", "Ore Lavorate", "Ore Target", "Credito/Debito"]]
                            st.dataframe(display_df, use_container_width=True)
                        
                        with col2:
                            # Crea un grafico che mostra le ore lavorate vs target
                            fig = px.bar(
                                hours_df, 
                                x="Infermiere", 
                                y=["Ore Lavorate", "Ore Target"],
                                barmode="group",
                                title="Ore Lavorate vs Ore Contrattuali Target",
                                color_discrete_map={"Ore Lavorate": "#1f77b4", "Ore Target": "#ff7f0e"}
                            )
                            fig.update_layout(xaxis_title="Infermiere", yaxis_title="Ore")
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Aggiungi un grafico che mostra le deviazioni
                            deviation_df = hours_df.copy()
                            deviation_df["Colore"] = deviation_df["Deviazione"].apply(
                                lambda x: "Positiva (Credito)" if x >= 0 else "Negativa (Debito)"
                            )
                            
                            fig2 = px.bar(
                                deviation_df,
                                x="Infermiere",
                                y="Deviazione",
                                color="Colore",
                                title="Deviazioni dalle Ore Contrattuali",
                                color_discrete_map={
                                    "Positiva (Credito)": "green",
                                    "Negativa (Debito)": "red"
                                }
                            )
                            fig2.update_layout(xaxis_title="Infermiere", yaxis_title="Ore di Differenza")
                            st.plotly_chart(fig2, use_container_width=True)
                    else:
                        # Visualizzazione semplice se non ci sono deviazioni
                        hours_df = pd.DataFrame({
                            "Infermiere": list(hours_worked.keys()),
                            "Ore Lavorate": list(hours_worked.values())
                        })
                        
                        # Crea due colonne
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.dataframe(hours_df, use_container_width=True)
                        
                        with col2:
                            fig = px.bar(hours_df, x="Infermiere", y="Ore Lavorate", 
                                        title="Ore Lavorate per Infermiere")
                            fig.update_layout(xaxis_title="Infermiere", yaxis_title="Ore")
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Genera una pianificazione per visualizzarla qui.")
    
    def show_analysis(self, tab, schedule_df):
        """Mostra l'analisi della pianificazione"""
        with tab:
            if schedule_df is not None:
                st.subheader("📊 Analisi della Pianificazione")
                
                # Prepara i dati per l'analisi
                data = schedule_df.melt(id_vars=['Data'], 
                                      var_name='Infermiere', 
                                      value_name='Turno')
                
                # Aggiungi giorno della settimana
                data['Data'] = pd.to_datetime(data['Data'])
                data['Giorno'] = data['Data'].dt.day_name()
                
                # Conteggio dei tipi di turno per infermiere
                st.subheader("Distribuzione dei Turni")
                shift_counts = data.groupby(['Infermiere', 'Turno']).size().unstack(fill_value=0)
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.dataframe(shift_counts, use_container_width=True)
                
                with col2:
                    fig = px.bar(data, x="Infermiere", color="Turno", 
                               barmode="group", title="Turni per Infermiere")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Analisi per giorno della settimana
                st.subheader("Turni per Giorno della Settimana")
                weekday_counts = data.groupby(['Giorno', 'Turno']).size().unstack(fill_value=0)
                
                # Ordina i giorni della settimana
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                weekday_order_it = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
                mapping = dict(zip(weekday_order, weekday_order_it))
                
                # Sostituisci i nomi inglesi con quelli italiani
                weekday_counts.index = weekday_counts.index.map(lambda x: mapping.get(x, x))
                weekday_counts = weekday_counts.reindex(weekday_order_it)
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.dataframe(weekday_counts, use_container_width=True)
                
                with col2:
                    data['Giorno_it'] = data['Giorno'].map(mapping)
                    fig = px.bar(data, x="Giorno_it", color="Turno", 
                               barmode="group", title="Distribuzione dei Turni per Giorno")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Weekend lavorati
                st.subheader("Analisi Weekend")
                data['Weekend'] = data['Giorno_it'].isin(['Sabato', 'Domenica'])
                weekend_data = data[data['Weekend']].copy()
                
                weekend_counts = weekend_data.groupby(['Infermiere', 'Turno']).size().unstack(fill_value=0)
                if 'Riposo' in weekend_counts.columns:
                    weekend_counts['Weekend Liberi'] = weekend_counts['Riposo'] // 2  # Approssimazione
                
                st.dataframe(weekend_counts, use_container_width=True)
                
                # Visualizzazione del calendario
                st.subheader("Calendario Turni")
                calendar_df = schedule_df.copy()
                calendar_df['Data'] = pd.to_datetime(calendar_df['Data'])
                calendar_df['Giorno'] = calendar_df['Data'].dt.day
                calendar_df.set_index('Giorno', inplace=True)
                del calendar_df['Data']
                
                st.dataframe(calendar_df, use_container_width=True)
            else:
                st.info("Genera una pianificazione per visualizzare l'analisi qui.")
    
    def show_preferences_input(self, tab, num_nurses, date_start, date_end):
        """Mostra l'interfaccia per l'inserimento delle preferenze"""
        with tab:
            st.subheader("🔍 Inserisci Preferenze Infermieri")
            
            # Converti date in oggetti datetime se necessario
            if isinstance(date_start, str):
                date_start = datetime.datetime.strptime(date_start, "%Y-%m-%d").date()
            if isinstance(date_end, str):
                date_end = datetime.datetime.strptime(date_end, "%Y-%m-%d").date()
            
            # Genera le date per il periodo
            delta = date_end - date_start
            dates = [date_start + datetime.timedelta(days=i) for i in range(delta.days + 1)]
            
            # Crea un DataFrame per le preferenze
            if 'preferences_df' not in st.session_state:
                # Inizializza il DataFrame delle preferenze
                preferences_data = []
                for date in dates:
                    row = {'Data': date}  # Usa direttamente l'oggetto date invece della stringa
                    for n in range(num_nurses):
                        row[f'Infermiere {n+1} Mattino'] = False
                        row[f'Infermiere {n+1} Pomeriggio'] = False
                    preferences_data.append(row)
                st.session_state.preferences_df = pd.DataFrame(preferences_data)
            else:
                # Verifica che le date nel DataFrame corrispondano a quelle richieste
                current_dates = set(st.session_state.preferences_df['Data'].dt.date if hasattr(st.session_state.preferences_df['Data'], 'dt') else st.session_state.preferences_df['Data'])
                requested_dates = set(dates)
                
                if current_dates != requested_dates:
                    # Ricostruisci il DataFrame se le date sono cambiate
                    preferences_data = []
                    for date in dates:
                        row = {'Data': date}
                        for n in range(num_nurses):
                            row[f'Infermiere {n+1} Mattino'] = False
                            row[f'Infermiere {n+1} Pomeriggio'] = False
                        preferences_data.append(row)
                    st.session_state.preferences_df = pd.DataFrame(preferences_data)
            
            # Mostra il DataFrame come una tabella editabile
            st.write("Seleziona i turni preferiti per ogni infermiere:")
            edited_df = st.data_editor(
                st.session_state.preferences_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Data': st.column_config.DateColumn(
                        'Data',
                        help="Data del turno",
                        format="DD/MM/YYYY",
                        step=86400,  # Un giorno in secondi
                    ),
                    **{f'Infermiere {n+1} Mattino': st.column_config.CheckboxColumn(
                        f'Inf {n+1} - Matt',
                        help=f"Seleziona se l'infermiere {n+1} preferisce il turno di mattina"
                    ) for n in range(num_nurses)},
                    **{f'Infermiere {n+1} Pomeriggio': st.column_config.CheckboxColumn(
                        f'Inf {n+1} - Pom',
                        help=f"Seleziona se l'infermiere {n+1} preferisce il turno di pomeriggio"
                    ) for n in range(num_nurses)}
                }
            )
            
            # Aggiorna il DataFrame delle preferenze nello stato della sessione
            st.session_state.preferences_df = edited_df
            
            # Bottone per salvare le preferenze
            if st.button("Salva Preferenze"):
                st.success("Preferenze salvate con successo!")
            
            # Restituisci il dizionario delle preferenze nel formato richiesto dal modello
            preferences = {}
            for _, row in edited_df.iterrows():
                date_obj = row['Data']  # Ora è già un oggetto date
                
                if isinstance(date_obj, str):  # Per sicurezza, gestisci anche il caso di stringhe
                    date_obj = datetime.datetime.strptime(date_obj, '%Y-%m-%d').date()
                
                day_idx = (date_obj - date_start).days
                
                for n in range(num_nurses):
                    # Turno mattina (indice 0)
                    if row[f'Infermiere {n+1} Mattino']:
                        preferences[(n, day_idx, 0)] = 1
                    
                    # Turno pomeriggio (indice 1)
                    if row[f'Infermiere {n+1} Pomeriggio']:
                        preferences[(n, day_idx, 1)] = 1
            
            return preferences
    
    def show_message(self, message, type="info"):
        """Mostra un messaggio all'utente"""
        if type == "info":
            st.info(message)
        elif type == "success":
            st.success(message)
        elif type == "warning":
            st.warning(message)
        elif type == "error":
            st.error(message)
    
    def download_button(self, df, filename):
        """Aggiunge un bottone per scaricare la pianificazione"""
        if df is not None:
            csv = df.to_csv(index=False)
            
            # Fix: Create a BytesIO object to write the Excel file
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Pianificazione')
            excel_data = excel_buffer.getvalue()
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Scarica CSV",
                    data=csv,
                    file_name=f"{filename}.csv",
                    mime="text/csv"
                )
            with col2:
                st.download_button(
                    label="📥 Scarica Excel",
                    data=excel_data,
                    file_name=f"{filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
