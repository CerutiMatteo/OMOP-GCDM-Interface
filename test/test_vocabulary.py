import streamlit as st
from src.vocabularyResolver import search_concepts

def main():
    st.title("OMOP Vocabulary Resolver - Test")

    term = st.text_input(
        "Search clinical concept",
        value="Hereditary macular dystrophy"
    )

    if st.button("Search"):
        with st.spinner("Searching OMOP vocabularies..."):
            try:
                results = search_concepts(term, limit=20)

                st.write(f"Found {len(results)} results")
                st.dataframe(results, use_container_width=True)

            except Exception as e:
                st.error(f"Error: {e}")

if __name__ == "__main__":
    main()