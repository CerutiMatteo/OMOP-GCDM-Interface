
SCHEMA_SEMANTICS = {
    "variant_annotation": {
        "description": (
            "Contains annotations associated with genomic variants."
        ),
        "relationships": [
            {
                "column": "variant_occurrence_id",
                "references_table": "variant_occurrence",
                "references_column": "variant_occurrence_id"
            }
        ],
        "columns": {
            "annotation_field": (
                "Identifies the annotation type, such as "
                "'vep_consequence'."
            ),
            "value_as_string": (
                "Stores the annotation value. For VEP consequences, "
                "examples include 'stop_gained'."
            )
        }
    },

    "variant_occurrence": {
        "description": (
            "Contains genomic variant occurrences associated "
            "with biological specimens. Each variant can reference "
            "up to two target genes through target_gene1_id "
            "and target_gene2_id."
        ),
        "columns": {
            "target_gene1_id": (
                "Foreign key referencing target_gene.target_gene_id. "
                "Identifies the first gene associated with the variant."
            ),
            "target_gene2_id": (
                "Foreign key referencing target_gene.target_gene_id. "
                "Identifies the second gene associated with the variant. "
                "When retrieving all genes associated with variants, "
                "both target_gene1_id and target_gene2_id must be considered."
            )
        }
    }
}
