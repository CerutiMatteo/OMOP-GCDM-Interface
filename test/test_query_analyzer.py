from src.queryAnalyzer import analyze_query


sql = """
SELECT
    p.person_id,
    c.condition_concept_id
FROM cdm.person AS p
INNER JOIN cdm.condition_occurrence AS c
    ON p.person_id = c.person_id
WHERE c.condition_concept_id = 201826;
"""

result = analyze_query(sql)

print("\nTABLES:")
for table in result["tables"]:
    print(table)

print("\nCOLUMNS:")
for column in result["columns"]:
    print(column)

print("\nJOINS:")
for join in result["joins"]:
    print(join)
