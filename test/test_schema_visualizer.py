from src.queryAnalyzer import analyze_query
from src.schemaVisualizer import visualize_query_structure


def test_schema_visualizer():

    sql = """
    SELECT
        p.person_id,
        c.condition_concept_id
    FROM cdm.person AS p
    INNER JOIN cdm.condition_occurrence AS c
        ON p.person_id = c.person_id
    WHERE c.condition_concept_id = 201826;
    """

    # Extract tables, columns and JOINs from SQL.
    analysis = analyze_query(sql)

    # Generate the Graphviz diagram.
    diagram = visualize_query_structure(analysis)

    # Save the diagram as a PNG image.
    output_path = diagram.render(
        filename="test/query_structure",
        format="png",
        cleanup=True
    )

    print(f"Diagram generated: {output_path}")


if __name__ == "__main__":
    test_schema_visualizer()
