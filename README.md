# Sistema di Pianificazione Turni Infermieri

Un'applicazione Streamlit per la pianificazione automatica dei turni degli infermieri utilizzando OR-Tools.

## Funzionalità

- Pianificazione automatica dei turni mensili per gli infermieri
- Supporto per preferenze degli infermieri
- Analisi dettagliata della pianificazione
- Rispetto dei vincoli legali (max 6 giorni consecutivi di lavoro)
- Visualizzazione grafica della distribuzione dei turni
- Esportazione della pianificazione in formato CSV ed Excel

## Requisiti

L'applicazione richiede Python 3.7+ e le seguenti librerie:

- streamlit
- ortools
- pandas
- numpy
- plotly
- openpyxl

## Installazione

1. Clona il repository:
```
git clone https://github.com/yourusername/nurse_scheduling.git
cd nurse_scheduling
```

2. Installa le dipendenze:
```
pip install -r requirements.txt
```

## Utilizzo

1. Avvia l'applicazione:
```
streamlit run controller.py
```

2. Nell'interfaccia web:
   - Imposta il numero di infermieri
   - Seleziona anno e mese per la pianificazione
   - Inserisci le preferenze degli infermieri nella scheda "Preferenze"
   - Clicca su "Genera Pianificazione" per creare il piano turni
   - Visualizza e analizza la pianificazione nelle schede "Pianificazione" e "Analisi"
   - Scarica la pianificazione in formato CSV o Excel

## Struttura MVC

L'applicazione segue il pattern Model-View-Controller:

- **Model** (`model.py`): Contiene la logica di pianificazione e risoluzione dei vincoli utilizzando OR-Tools
- **View** (`view.py`): Gestisce l'interfaccia utente con Streamlit
- **Controller** (`controller.py`): Coordina le interazioni tra modello e vista, gestisce lo stato dell'applicazione

## Vincoli implementati

- Massimo 6 giorni consecutivi di lavoro
- Nessun passaggio da turno pomeridiano a turno mattutino
- Almeno due weekend liberi al mese per ogni infermiere
- Distribuzione equa del carico di lavoro
- Ottimizzazione delle preferenze degli infermieri

## Licenza

Questo progetto è disponibile con licenza MIT. 