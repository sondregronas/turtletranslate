with open("docs/index.md", "r", encoding="utf-8") as f:
    md = f.read()

from turtletranslate import file_handler

prepend_md = """
> [!NOTE] Dette er en AI generert oversettelse som kan inneholde feil og mangler.
"""

frontmatter, sections = file_handler.parse(md, prepend_md=prepend_md)
print(frontmatter)
for s in sections:
    print("#" * 10)
    print(s)

# Output:
output = file_handler.reconstruct(frontmatter, sections)
# print(output)
