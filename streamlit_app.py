import praw
import re
import pandas as pd
from thefuzz import process  # Updated to use thefuzz
import wbdata
import matplotlib.pyplot as plt
import streamlit as st

#######################################
# 1. STREAMLIT SETUP & USER INPUT
#######################################

st.title("Migration Patterns Analysis")

# User input for subreddit and number of posts
subreddit_name = st.text_input("Enter subreddit name:", "IWantOut")
num_posts = st.number_input("Number of posts to fetch:", min_value=10, max_value=500, value=100, step=10)

# Replace with your own credentials from https://www.reddit.com/prefs/apps
reddit = praw.Reddit(
    client_id="wqQzEhvlInEto5FqaqTNBw",
    client_secret="492s5Fif0p1uI29RxisIgCLJbzqLPQ",
    user_agent="YOUR_USER_AGENT"
)

#######################################
# 2. FETCH REDDIT POSTS
#######################################

all_data = []
st.write(f"Fetching {num_posts} posts from subreddit: {subreddit_name}...")

try:
    subreddit = reddit.subreddit(subreddit_name)
    for submission in subreddit.hot(limit=num_posts):
        title = submission.title
        all_data.append({"post_title": title})

    st.success("Posts fetched successfully!")
except Exception as e:
    st.error(f"Failed to fetch posts: {e}")

#######################################
# 3. TEXT PROCESSING & COUNTRY EXTRACTION
#######################################

filtered_data = []
for item in all_data:
    text = item["post_title"].lower()  # Lowercase text
    text = re.sub(r"http\S+", "", text)  # Remove URLs
    text = re.sub(r"[^a-zA-Z0-9\s\->]", "", text)  # Keep alphanumeric characters, spaces, and "->"
    text = re.sub(r"\s+", " ", text).strip()  # Remove extra whitespace
    item["cleaned_comment"] = text

    # Regex to extract countries before and after the arrow
    arrow_match = re.search(r"([a-zA-Z]+)\s*->\s*([a-zA-Z]+)", text)
    if arrow_match:
        item["current_country"] = arrow_match.group(1)  # Country before the arrow
        item["desired_country"] = arrow_match.group(2)  # Country after the arrow
        filtered_data.append(item)  # Only include posts with a valid arrow match

# Convert to DataFrame
df = pd.DataFrame(filtered_data)
st.write("Extracted migration data:")
st.dataframe(df)

#######################################
# 4. COUNT OCCURRENCES & FETCH GDP DATA
#######################################

# Count occurrences of current and desired countries
current_counts = df["current_country"].value_counts().reset_index()
current_counts.columns = ["country", "leaving_mentions"]

desired_counts = df["desired_country"].value_counts().reset_index()
desired_counts.columns = ["country", "moving_mentions"]

# Merge leaving and moving mentions
country_mentions = pd.merge(current_counts, desired_counts, on="country", how="outer").fillna(0)

# Fetch GDP per capita data from World Bank API
gdp_data = wbdata.get_data("NY.GDP.PCAP.CD")  # Fetch all available data for GDP per capita
gdp_df = pd.DataFrame([
    {"country": entry["country"]["value"], "gdp_per_capita": entry["value"]}
    for entry in gdp_data if entry["value"] is not None
])

# Fuzzy match country names using thefuzz
matched_countries = []
for country in country_mentions["country"]:
    match = process.extractOne(country, gdp_df["country"], score_cutoff=80)  # Adjust score_cutoff as needed
    if match:
        matched_countries.append((country, match[0], match[1]))
    else:
        matched_countries.append((country, None, 0))

matched_df = pd.DataFrame(matched_countries, columns=["country", "matched_country", "score"])
matched_gdp = pd.merge(country_mentions, matched_df, on="country")
matched_gdp = pd.merge(matched_gdp, gdp_df, left_on="matched_country", right_on="country", suffixes=("", "_gdp")).drop(columns=["country_gdp"])

#######################################
# 5. FINAL DATAFRAME
#######################################

# Group by matched_country and aggregate values
final_df = matched_gdp.groupby("matched_country").agg({
    "leaving_mentions": "sum",
    "moving_mentions": "sum",
    "gdp_per_capita": "mean"  # Average GDP per capita if duplicates exist
}).reset_index()

# Rename columns for clarity
final_df.rename(columns={"matched_country": "country"}, inplace=True)

st.write("Final Data:")
st.dataframe(final_df)

#######################################
# 6. PLOT DATA IN STREAMLIT
#######################################

# Scatterplot: Origin countries vs GDP
st.subheader("GDP per Capita vs Leaving Mentions")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(final_df["gdp_per_capita"], final_df["leaving_mentions"], alpha=0.7)
ax.set_title("GDP per Capita vs Leaving Mentions")
ax.set_xlabel("GDP per Capita")
ax.set_ylabel("Leaving Mentions")
ax.grid()
st.pyplot(fig)

# Scatterplot: Destination countries vs GDP
st.subheader("GDP per Capita vs Moving Mentions")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(final_df["gdp_per_capita"], final_df["moving_mentions"], alpha=0.7, color="orange")
ax.set_title("GDP per Capita vs Moving Mentions")
ax.set_xlabel("GDP per Capita")
ax.set_ylabel("Moving Mentions")
ax.grid()
st.pyplot(fig)

#######################################
# 7. EXPORT DATAFRAME
#######################################

csv = final_df.to_csv(index=False)
st.download_button(
    label="Download Data as CSV",
    data=csv,
    file_name="migration_analysis.csv",
    mime="text/csv"
)
