import streamlit as st # gestisce l'interfaccia web che vede l'utente
import psycopg         # permette al codice python di comunicare con PostgreSQL e eseguire interrogazioni SQL

# LEGGO LA CONF DEL DATABASE
db_config = st.secrets["connections"]["omop"]

def connect_db():
    return psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    )

# TITOLO, ASPETTO, DESCRIZIONE DELLA PAGINA
st.set_page_config(page_title="OMOP G-CDM Interface", page_icon="🧬", layout="wide")
st.title("🧬 OMOP G-CDM Interface")
st.write("Interfaccia in linguaggio naturale per interrogare il database OMOP G-CDM.")

# CAMPO PER LA DOMANDA DELL'UTENTE
question = st.text_input("Inserisci una domanda sui dati clinici e genomici:")

# PULSANTE PER AVVIARE L'INTERROGAZIONE
if st.button("Esegui interrogazione"):
    if question: # is question not empty?
        st.info(f"Domanda inserita: {question}")
    else:
        st.warning("Inserisci una domanda prima di procedere.")

st.subheader("Test connessione PostgreSQL")

if st.button("Verifica connessione al database"):
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM cdm.person;")
                numero_pazienti = cur.fetchone()[0]

        st.success("Connessione al database riuscita!")
        st.write(f"Numero di pazienti presenti: {numero_pazienti}")

    except psycopg.Error as e:
        st.error("Errore durante la connessione o l'interrogazione del database.")
        st.error(str(e))