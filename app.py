import streamlit as st
import psycopg

from textToSQL import generate_sql

# Configure the Streamlit page.
st.set_page_config(
    page_title="OMOP G-CDM Interface",
    page_icon="🧬",
    layout="wide"
)

# Read the PostgreSQL connection settings from Streamlit secrets.
db_config = st.secrets["connections"]["omop"]

# Create a read-only connection to the PostgreSQL database.
def connect_db():
    return psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    )

# Display the application title, description and subheader.
st.title("🧬 OMOP G-CDM Interface")
st.write("Interfaccia in linguaggio naturale per interrogare il database OMOP G-CDM.")
st.subheader("Interrogazione in linguaggio naturale")

# Question field
question = st.text_input("Inserisci una domanda sui dati clinici e genomici:", placeholder="Es. Quanti pazienti sono presenti nel database?")

# Button to generate a SQL.
if st.button("Genera SQL", type="primary"):

    # Check that the user entered a non-empty question.
    if question.strip():

        # Display a loading indicator (spinner) while Gemini processes the request.
        with st.spinner("Generazione della query SQL in corso..."): # program shows the spinner until the execution of this block is finished

            try:
                # Generate SQL using the Text-to-SQL module.
                sql = generate_sql(question)

                # Display the SQL query returned by Gemini.
                st.subheader("Query SQL generata")
                st.code(sql, language="sql")

                # Inform the user that the query has not been executed.
                st.info("La query è stata generata, ma non è stata ancora eseguita sul database.")

            # Handle errors during SQL generation.
            except Exception as e:
                st.error("Errore durante la generazione della query SQL.")
                st.error(str(e))

    else:
        st.warning("Inserisci una domanda prima di procedere.")


# 'DIAGNOSTICS' / 'DIAGNOSTICA':
with st.expander("Diagnostica PostgreSQL"):

    st.write("Verifica la connessione al database OMOP G-CDM.")

    # Test the PostgreSQL connection only when requested.
    if st.button("Verifica connessione al database"):

        try:
            # Open a read-only database connection.
            with connect_db() as conn:
                with conn.cursor() as cur:

                    # Execute a predefined query to test the connection.
                    cur.execute("SELECT COUNT(*) FROM cdm.person;")
                    numero_pazienti = cur.fetchone()[0]

            # Display the connection test result.
            st.success("Connessione al database riuscita!")
            st.write(f"Numero di pazienti presenti: {numero_pazienti}")

        # Handle PostgreSQL connection or query errors.
        except psycopg.Error as e:
            st.error(
                "Errore durante la connessione o "
                "l'interrogazione del database."
            )
            st.error(str(e))