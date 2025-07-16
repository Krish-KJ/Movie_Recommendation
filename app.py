import streamlit as st
import os
from dotenv import load_dotenv
import requests
from urllib.parse import quote

# Load API key
try:
    tmdb_api_key = st.secrets["TMDB_API_KEY"]
except Exception:
    load_dotenv()
    tmdb_api_key = os.getenv("TMDB_API_KEY")

def fetch_movie_data_from_api(movie_title):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={quote(movie_title)}"
    try:
        response = requests.get(url, timeout=10).json()
    except Exception as e:
        st.error(f"Error fetching movie data: {e}")
        return None, None

    if response['results']:
        best_match = sorted(response['results'], key=lambda x: x.get('popularity', 0), reverse=True)[0]
        movie_id = best_match['id']
        details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={tmdb_api_key}&append_to_response=similar,credits"
        try:
            details = requests.get(details_url, timeout=10).json()
        except Exception as e:
            st.error(f"Error fetching movie details: {e}")
            return None, None

        return {
            "title": details.get("title"),
            "genre": [g["name"] for g in details.get("genres", [])],
            "year": details.get("release_date", "")[:4],
            "cast": [c["name"] for c in details.get("credits", {}).get("cast", [])[:5]],
            "director": [c["name"] for c in details.get("credits", {}).get("crew", []) if c["job"] == "Director"],
            "overview": details.get("overview", "No description available."),
            "rating": details.get("vote_average", "N/A"),
            "similar": details.get("similar", {}).get("results", [])
        }, movie_id
    return None, None

def fetch_movie_collection(movie_id):
    collection_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={tmdb_api_key}"
    try:
        details = requests.get(collection_url, timeout=10).json()
    except Exception as e:
        st.error(f"Error fetching collection for movie_id {movie_id}: {e}")
        return [], None

    collection = details.get("belongs_to_collection")
    collection_id = collection.get("id") if collection else None
    if collection_id:
        coll_url = f"https://api.themoviedb.org/3/collection/{collection_id}?api_key={tmdb_api_key}"
        try:
            coll = requests.get(coll_url, timeout=10).json()
        except Exception as e:
            st.error(f"Error fetching collection details: {e}")
            return [], collection_id
        return [item['title'] for item in coll.get("parts", []) if 'release_date' in item and item['release_date'][:4].isdigit()], collection_id
    return [], None

def fetch_poster(movie_title):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={quote(movie_title)}"
    try:
        response = requests.get(url, timeout=10).json()
    except:
        return "https://via.placeholder.com/300x450?text=Error"

    if response['results'] and response['results'][0].get('poster_path'):
        return f"https://image.tmdb.org/t/p/w500{response['results'][0]['poster_path']}"
    return "https://via.placeholder.com/300x450?text=No+Poster"

def recommend(movie_title):
    movie_info, movie_id = fetch_movie_data_from_api(movie_title)
    if not movie_info:
        return [("Movie not found", "https://via.placeholder.com/300x450?text=Not+Found", "")], movie_title.title()

    recommendations = []
    used_titles = set()
    original_genres = set(movie_info.get("genre", []))
    original_year = int(movie_info.get("year", "2000"))

    sequels, collection_id = fetch_movie_collection(movie_id)
    for title in sequels:
        if title.lower() != movie_info['title'].lower():
            poster = fetch_poster(title)
            recommendations.append((title, poster, "From the same series/collection"))
            used_titles.add(title)
        if len(recommendations) >= 5:
            break

    if len(recommendations) < 5:
        sorted_similars = sorted(
            movie_info['similar'],
            key=lambda x: x.get("release_date", "1900"),
            reverse=True
        )
        for movie in sorted_similars:
            title = movie.get("title")
            release_date = movie.get("release_date")
            if not title or not release_date or title in used_titles:
                continue
            year = int(release_date[:4])
            if year < original_year - 2:
                continue
            genre_url = f"https://api.themoviedb.org/3/movie/{movie['id']}?api_key={tmdb_api_key}"
            try:
                genre_resp = requests.get(genre_url, timeout=10).json()
                movie_genres = set([g['name'] for g in genre_resp.get('genres', [])])
            except:
                continue
            if not original_genres & movie_genres:
                continue
            poster = fetch_poster(title)
            recommendations.append((title, poster, "Similar movie based on genre and recency"))
            used_titles.add(title)
            if len(recommendations) >= 5:
                break

    if len(recommendations) < 5:
        genre_map_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={tmdb_api_key}&language=en-US"
        genre_data = requests.get(genre_map_url).json()
        genre_ids = []
        for g in original_genres:
            for g_map in genre_data.get('genres', []):
                if g_map['name'].lower() == g.lower():
                    genre_ids.append(str(g_map['id']))
        if genre_ids:
            fallback_url = (
                f"https://api.themoviedb.org/3/discover/movie?api_key={tmdb_api_key}"
                f"&sort_by=popularity.desc&with_genres={','.join(genre_ids)}"
                f"&primary_release_date.gte={original_year}&language=en-US&page=1"
            )
            fallback_resp = requests.get(fallback_url).json()
            for movie in fallback_resp.get("results", []):
                title = movie.get("title")
                if title and title not in used_titles:
                    poster = fetch_poster(title)
                    recommendations.append((title, poster, "Genre-based fallback recommendation"))
                    used_titles.add(title)
                if len(recommendations) >= 5:
                    break

    return recommendations, movie_info

# UI
st.set_page_config(page_title="Movie Recommender", layout="wide")

st.markdown("""
    <h1 style='text-align: center; color: #FF4B4B;'>🎬 Movie Recommendation App</h1>
    <h4 style='text-align: center; color: grey;'>Find movies similar to your favorite ones</h4>
""", unsafe_allow_html=True)

st.markdown("---")

with st.form("movie_form"):
    movie_input = st.text_input("Enter a movie you like:", "")
    submit = st.form_submit_button("🔍 Recommend")

if submit and movie_input:
    with st.spinner("Fetching recommendations..."):
        recommendations, movie_info = recommend(movie_input)

    st.markdown(f"### 📽️ Recommendations for: `{movie_info['title']}`")

    with st.expander("📋 Movie Info"):
        st.write(f"**Genres:** {', '.join(movie_info['genre'])}")
        st.write(f"**Release Year:** {movie_info['year']}")
        st.write(f"**Cast:** {', '.join(movie_info['cast'])}")
        st.write(f"**Director:** {', '.join(movie_info['director'])}")
        st.write(f"**Rating:** {movie_info['rating']}")
        st.write(f"**Overview:** {movie_info['overview']}")

    cols = st.columns(5)
    for idx, (title, poster_url, source) in enumerate(recommendations[:5]):
        with cols[idx]:
            st.image(poster_url, caption=title, use_container_width=True)
            st.caption(source)

st.markdown("---")
st.markdown("<p style='text-align: center; color: grey;'>Built with ❤️ using Streamlit and TMDB API</p>", unsafe_allow_html=True)
