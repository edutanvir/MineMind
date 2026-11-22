
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client()

prompt = """
You are the technical AI assistant for MineMind, a Canadian mining
data intelligence project.

PROJECT CONTEXT:

MineMind is being developed as a data engineering and analytics
application focused on exploring Canadian mining locations and
understanding mineral production trends.

Confirmed data sources:
1. Natural Resources Canada (NRCan) 900A mining dataset.
2. Statistics Canada Table 16-10-0019-01, containing mineral
   production statistics.

Planned technology stack:
- Python for data engineering
- GeoPandas for geospatial data processing
- Pandas and NumPy for data transformation
- Parquet for analytical data storage
- DuckDB for analytical querying
- Streamlit for the interactive application
- Plotly and Folium for visualizations
- Gemini API for natural-language assistance

Planned architecture:
- Bronze: Preserve and ingest original source data.
- Silver: Clean, standardize, and process the source datasets.
- Gold: Create analytical datasets for mining locations and
  mineral production analysis.
- Application: Allow users to explore mining information,
  geographical distributions, and production trends.

IMPORTANT RULES:
- Do not invent datasets, columns, metrics, or capabilities.
- Do not claim that any pipeline or feature is already implemented.
- Distinguish clearly between planned and implemented functionality.
- Do not claim forecasting, automated updates, or real-time
  intelligence unless explicitly supported.
- Explain technical concepts in practical terms.

QUESTION:

Explain how data engineering creates value in MineMind.
Focus on the actual data flow, data transformation, integration
of geospatial and production information, and the analytical
questions users will eventually be able to answer.

Use a professional but natural tone.
Avoid generic marketing language.
Keep the response under 250 words.
"""

response = client.models.generate_content(
    model=os.environ["GEMINI_MODEL"],
    contents=prompt
)

print("\n========== MINEMIND AI RESPONSE ==========\n")
print(response.text)
print("\n==========================================\n")
