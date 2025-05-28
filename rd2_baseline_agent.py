# === IMPORTS ===
import arxiv
import requests
from scholarly import scholarly
from gnews import GNews
from datetime import datetime
# Import the OpenAI client
from openai import OpenAI
from fpdf import FPDF
from google.colab import files
from docx import Document # Moved import here

# === CONFIG ===
# Instantiate the OpenAI client
# Replace "sk-..." with your actual secret API key
# Alternatively, set the OPENAI_API_KEY environment variable
client = OpenAI(api_key="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")
lens_token = "eyJ..."             # from https://www.lens.org


# === SEARCH ARXIV ===
def search_arxiv(query, start_date, end_date):
    search = arxiv.Search(query=query, max_results=5, sort_by=arxiv.SortCriterion.SubmittedDate)
    results = []
    for result in search.results():
        pub_date = result.published.date()
        if start_date <= pub_date <= end_date:
            results.append({
                "title": result.title,
                "summary": result.summary,
                "url": result.entry_id,
                "published": str(pub_date)
            })
    return results

# === SEARCH SEMANTIC SCHOLAR ===
def search_semantic_scholar(query, max_results=5):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,url,year,citationCount"
    }

    response = requests.get(url, params=params)
    results = []
    if response.status_code == 200:
        for paper in response.json().get("data", []):
            results.append({
                "title": paper.get("title", "No title"),
                "summary": paper.get("abstract", "No abstract"),
                "url": paper.get("url", "N/A"),
                "published": paper.get("year", "Unknown"),
                "citations": paper.get("citationCount", 0)
            })
    else:
        print("Semantic Scholar API error:", response.status_code, response.text)
    return results



# === SEARCH NEWS ===
def search_news(query, start_date, end_date):
    google_news = GNews()
    google_news.start_date = (start_date.year, start_date.month, start_date.day)
    google_news.end_date = (end_date.year, end_date.month, end_date.day)
    google_news.max_results = 5
    results = google_news.get_news(query)
    output = []
    for article in results:
        output.append({
            "title": article["title"],
            "summary": article.get("description", "No summary"),
            "url": article["url"],
            "published": str(article["published date"])
        })
    return output

# === SEARCH PATENTS ===
def search_lens_patents(query, start_year, end_year, token):
    url = "https://api.lens.org/patent/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"lens_id": query}},
                    {"range": {"publication_date": {"gte": f"{start_year}-01-01", "lte": f"{end_year}-12-31"}}}
                ]
            }
        },
        "size": 5,
        "include": ["lens_id", "title", "abstract", "publication_date"]
    }

    response = requests.post(url, headers=headers, json=payload)
    results = []
    if response.status_code == 200:
        for res in response.json().get("data", []):
            results.append({
                "title": res.get("title", [{}])[0].get("text", "No title"),
                "summary": res.get("abstract", "No abstract"),
                "url": f"https://www.lens.org/{res.get('lens_id')}",
                "published": res.get("publication_date", "Unknown")
            })
    else:
        print("Lens API error:", response.status_code, response.text)
    return results

# === COLLECT SOURCES ===
def collect_sources(tech_area, start, end):
    sources = []
    print("Searching arXiv...")
    sources += search_arxiv(tech_area, start, end)

    print("Searching semantic scholar...")
    sources += search_semantic_scholar(tech_area)

    print("Searching News...")
    sources += search_news(tech_area, start, end)

    print("Searching Patents...")
    sources += search_lens_patents(tech_area, start.year, end.year, lens_token)

    return sources

# === SUMMARIZE ===
def summarize_results(results, tech_area, end_date):
    joined_text = "\n\n".join(
        [f"Title: {r['title']}\nSummary: {r['summary']}\nURL: {r['url']}" for r in results]
    )
    prompt = f"""
You are a technical analyst supporting an R&D tax claim in the UK.

Summarize the current state of the art at the **end of the specified time period** in the area of: \"{tech_area}\".
Focus strictly on:
- What was demonstrably known, implemented, or practiced
- Existing technical limitations or barriers that were not yet overcome
- Do not include future predictions or speculative trends
- Cite relevant URLs
- Highlight sources with high citation counts where applicable

The summary should reflect the situation **as of {end_date}**.  # Use end_date here

Sources:\n{joined_text}
Summary:
"""
    # Use the new syntax for creating chat completions
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # You can use other models like "gpt-4" if available
        messages=[
            {"role": "system", "content": "You are a helpful technical analyst."},
            {"role": "user", "content": prompt}
        ]
    )
    # Access the content from the new response object structure
    return response.choices[0].message.content

# === INTERACTIVE RUN ===
if __name__ == "__main__":
    tech_area = input("Enter the technology area (e.g., 'AI in medical imaging'): ")
    start_date_str = input("Enter start date (YYYY-MM-DD): ")
    end_date_str = input("Enter end date (YYYY-MM-DD): ")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    print("Collecting data...")
    sources = collect_sources(tech_area, start_date, end_date)

    print("Summarizing...")
    # Pass end_date to the summarize_results function
    summary = summarize_results(sources, tech_area, end_date)

    print("Generating report...")
    # Pass the 'sources' variable to the generate_docx_report function
    filename = generate_docx_report(summary, sources)

    print(f"Report complete: {filename}")
    files.download(filename)

    # === STREAMLIT UI ===
st.title("R&D Baseline Agent")
st.markdown("Use this tool to generate a state-of-the-art baseline summary for R&D tax claims in the UK.")

tech_area = st.text_input("Technology Area", "natural language processing for voice assistants")
start_date = st.date_input("Start Date", date(2021, 1, 1))
end_date = st.date_input("End Date", date(2021, 3, 31))

if st.button("Generate Report"):
    with st.spinner("Collecting sources and generating summary..."):
        try:
            sources = collect_sources(tech_area, start_date, end_date)
            summary = summarize_results(sources, tech_area)
            filename = generate_docx_report(summary, sources)
            with open(filename, "rb") as f:
                st.download_button("Download DOCX Report", f, file_name=filename)
        except Exception as e:
            st.error(f"An error occurred: {e}")

pip install --upgrade openai

!pip install arxiv scholarly gnews openai fpdf python-docx requests

!pip install streamlit

!pip install python-docx
