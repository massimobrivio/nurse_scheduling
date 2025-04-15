# Pianificazione Turni Infermieri

Questa applicazione Streamlit permette di pianificare i turni mensili per infermieri e freelancer in base a preferenze, disponibilità e vincoli specifici.

## Funzionalità

- Configurazione del numero di infermieri e freelancer
- Impostazione di vincoli come weekend liberi e giorni consecutivi di lavoro
- Inserimento delle preferenze per gli infermieri
- Inserimento delle disponibilità per i freelancer
- Generazione automatica della pianificazione mensile
- Esportazione della pianificazione in Excel e CSV

## Requisiti

- Python 3.8 o superiore
- Pacchetti Python necessari (vedi requirements.txt)

## Installazione

1. Clona questo repository o scarica i file
2. Installa le dipendenze:

```bash
pip install -r requirements.txt
```

## Utilizzo

1. Avvia l'applicazione:

```bash
streamlit run controller.py
```

2. Nel browser, segui questi passaggi:
   - Configura i parametri di base nella scheda "Configurazione"
   - Inserisci le preferenze degli infermieri e le disponibilità dei freelancer nella scheda "Preferenze e Disponibilità"
   - Genera la pianificazione dalla scheda "Risultati"
   - Esporta i risultati in Excel o CSV

## Note Tecniche

- L'applicazione utilizza OR-Tools di Google per risolvere il problema di ottimizzazione
- Segue l'architettura Model-View-Controller (MVC)
- I file principali sono:
  - `model.py`: Logica di ottimizzazione e gestione dei dati
  - `view.py`: Interfaccia utente Streamlit
  - `controller.py`: Coordinamento tra modello e vista

## Vincoli Implementati

- Massimo numero di giorni consecutivi di lavoro
- Minimo numero di weekend liberi per infermiere
- Rispetto delle ore contrattuali mensili degli infermieri
- Nessun turno pomeridiano seguito da turno mattutino il giorno successivo
- Rispetto delle disponibilità dei freelancer
- Massimizzazione delle preferenze degli infermieri 