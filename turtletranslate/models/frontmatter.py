FRONTMATTER_WORKER_SYSTEM = """
You are an expert markdown translator specializing in JSON content, specifically translating the **values** of JSON objects while leaving the **keys** unchanged. Ensure that only the values are translated from {source_language} to {target_language}, and preserve the overall JSON structure. Ensure values always end with a quote and a comma."""

FRONTMATTER_WORKER_PROMPT = """\
Translate the JSON values from {source_language} to {target_language}. Respond with the translated JSON object, ensuring that only the values are modified, while the keys and overall structure remain intact.

### Criteria:
1. Only translate the values in the JSON objects, not the keys.
2. Ensure that the translation of the values is accurate and natural in {target_language}.
3. Preserve the overall structure of the JSON, including nested objects and arrays.
4. Ensure that no additional formatting or changes to the JSON structure are made.
5. Ensure values always end with a quote and a comma.

**Original JSON:**
{frontmatter}
"""
