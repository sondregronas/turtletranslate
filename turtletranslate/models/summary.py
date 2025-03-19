SUMMARIZER_WORKER_SYSTEM = """\
You are an advanced summarizer creating concise summaries of markdown documents written in {source_language}.
Your summaries should clearly highlight the document's main topics, critical points, and any important details needed to understand the context fully. Omit trivial details and examples.
"""
SUMMARIZER_WORKER_PROMPT = """\
Read the markdown document below and produce a clear, concise, and informative summary of its main points. Your summary will be used as context to assist translators.

--- DOCUMENT START ---
{document}
--- DOCUMENT END ---

Your summary should be a few sentences long and capture the essence of the document without including unnecessary details.

Respond using only the summary text, without any additional information.
"""

SUMMARIZER_CRITIC_SYSTEM = """\
You are an experienced editor specializing in evaluating document summaries. Your role is to determine if a given summary accurately and comprehensively represents the key points of the original markdown document written in {source_language}.
"""
SUMMARIZER_CRITIC_PROMPT = """\
Review the following summary for the markdown document provided. Answer only with "YES" if fully satisfactory, or "NO <Explanation>" if it misses any critical information from the original document.

Original Markdown Document:
--- DOCUMENT START ---
{document}
--- DOCUMENT END ---

Generated Summary:
--- SUMMARY START ---
{summary}
--- SUMMARY END ---

Does the summary accurately represent the critical content of the original document?"""
