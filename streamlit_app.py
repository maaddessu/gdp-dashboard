import praw
import re
import pandas as pd
from thefuzz import process  # Updated to use thefuzz
import wbdata
import matplotlib.pyplot as plt
import streamlit as st

#######################################
# 1. SET UP REDDIT & FETCH POSTS
#######################################

# Replace with your own credentials from https://www.reddit.com/prefs/apps
reddit = praw.Reddit(
    client_id="wqQzEhvlInEto5FqaqTNBw",
    client_secret="492s5Fif0p1uI29RxisIgCLJbzqLPQ",
    user_agent="YOUR_USER_AGENT"
)

# Parameters
subreddit_name = "IWantOut"  # Example subreddit, replace with your choice
num_posts = 10  # Number of posts to fetch
comment_limit = 1  # Number of top comments per post

all_data = []

# Fetch posts and comments
subreddit = reddit.subreddit(subreddit_name)
for submission in subreddit.hot(limit=num_posts):
    title = submission.title
    submission.comments.replace_more(limit=0)

    count = 0
    for comment in submission.comments.list():
        if hasattr(comment, "body"):
            all_data.append({
                "post_title": title
            })
            count += 1
            if count >= comment_limit:
                break

#######################################
# 2. TEXT PROCESSING & COUNTRY EXTRACTION
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
print(df)

#######################################
# 3. COUNT OCCURRENCES & FETCH GDP DATA
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

# Fuzzy match country names
matched_countries = []
for country in country_mentions["country"]:
    match = process.extractOne(country, gdp_df["country"])
    matched_countries.append((country, match[0], match[1] if match else 0))

matched_df = pd.DataFrame(matched_countries, columns=["country", "matched_country", "score"])
matched_gdp = pd.merge(country_mentions, matched_df, on="country")
matched_gdp = pd.merge(matched_gdp, gdp_df, left_on="matched_country", right_on="country", suffixes=("", "_gdp")).drop(columns=["country_gdp"])

#######################################
# 4. CREATE SCATTERPLOTS IN STREAMLIT
#######################################

st.title("Migration Patterns Analysis")

# Scatterplot: Origin countries vs GDP
st.subheader("GDP per Capita vs Leaving Mentions")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(matched_gdp["gdp_per_capita"], matched_gdp["leaving_mentions"], alpha=0.7)
ax.set_title("GDP per Capita vs Leaving Mentions")
ax.set_xlabel("GDP per Capita")
ax.set_ylabel("Leaving Mentions")
ax.grid()
st.pyplot(fig)

# Scatterplot: Destination countries vs GDP
st.subheader("GDP per Capita vs Moving Mentions")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(matched_gdp["gdp_per_capita"], matched_gdp["moving_mentions"], alpha=0.7, color="orange")
ax.set_title("GDP per Capita vs Moving Mentions")
ax.set_xlabel("GDP per Capita")
ax.set_ylabel("Moving Mentions")
ax.grid()
st.pyplot(fig)

#######################################
# 5. DISPLAY DATA & EXPORT BUTTON
#######################################

st.subheader("Data Preview")
st.dataframe(matched_gdp)

# Download CSV button
csv = matched_gdp.to_csv(index=False)
st.download_button(label="Download Data as CSV", data=csv, file_name="country_mentions_gdp.csv", mime="text/csv")
