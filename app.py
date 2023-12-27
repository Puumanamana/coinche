import numpy as np
import pandas as pd
from pathlib import Path
import streamlit as st
import re
from itertools import zip_longest
import sqlite3

st.set_page_config(layout="wide")

st.title("Coinche-moi STP")

url = "https://raw.githubusercontent.com/Puumanamana/coinche/main/assets/cards"

cards = [Path(url, f"{suit}_{value}.png")
         for suit in ["hearts", "diamonds", "spades", "clubs"]
         for value in ["7", "8", "9", "10", "jack", "queen", "king", "ace"]]
suits = {x: x.stem.split('_')[0] for x in cards}
symbols = dict(pique="♠", coeur="♥", carreau="♦", trefle="♣")

conn = sqlite3.connect('coinche.db')
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS coinche(hand, guess, color, comment)")
conn.commit()
conn.close()

def get_db():
    df = pd.read_sql(
        "SELECT * FROM coinche",
        con=sqlite3.connect('coinche.db'),
    )
    return df

def save_to_db():
    db_entry = (
        ",".join(x.stem for x in st.session_state.hand),
        st.session_state.guess,
        st.session_state.color,
        st.session_state.comment
    )
    conn = sqlite3.connect('coinche.db')
    c = conn.cursor()
    c.execute("INSERT INTO coinche (hand, guess, color, comment) VALUES (?, ?, ?, ?)", db_entry)
    conn.commit()
    # Close connection
    conn.close()

def random_hand():
    st.session_state["hand"] = np.random.choice(cards, 8, replace=False)

def sort_hand(hand):
    hand_df = pd.Series([card.stem for card in hand]).str.split("_", expand=True)
    hand_df.index = hand
    hand_df.columns = ["suit", "number"]
    hand_df["color"] = np.where(hand_df["suit"].isin(["hearts", "diamonds"]), "red", "black")

    # Find the most common color
    suits_found = hand_df.groupby("color").suit.agg(set)
    color_max = suits_found.map(len).idxmax()
    # Other color ('manually' set since all colors are not always present)
    other_color = [color for color in {"red", "black"} if color != color_max][0]

    # Alternate colors
    suit_order = [
        suit
        for suits in zip_longest(suits_found[color_max], suits_found[other_color])
        for suit in suits if suit is not None
    ]

    # Category order
    hand_df["suit"] = pd.Categorical(hand_df["suit"], suit_order)

    return hand_df.sort_values(["suit", "number"], ascending=False).index.astype(str).to_list()

tabs = st.tabs(["Jouer", "Historique"])

with tabs[0]:
    show_next = st.button("Prochaine main", on_click=random_hand, type="primary")

    if not "hand" in st.session_state:
        st.stop()

    st.image(sort_hand(st.session_state.hand), width=170)

    with st.form("mise"):
        cols = st.columns([1, 1, 2])
        with cols[0]:
            st.number_input(
                "Choisir une annonce : ", key="guess",
                min_value=0, max_value=270, value=80, step=10
            )
            st.selectbox(
                "Choisir une couleur : ",
                ["Coeur", "Carreau", "Pique", "Trèfle", "Sans atout", "Tout atout"],
                index=None, key="color"
            )
            st.text_area("Ajouter un commentaire :", key="comment")
            submitted = st.form_submit_button("Valider", on_click=save_to_db)

        if submitted:
            st.write(f"Mise : {st.session_state.guess}")

with tabs[1]:
    df = get_db()

    for row in df.itertuples():
        # hand = [Path(url, f"{card}.png") for card in row.hand.split(",")]
        hand = [Path("assets", "cards", f"{card}.png") for card in row.hand.split(",")]
        st.image(sort_hand(hand), width=170)
        st.metric(label="Mise", value=f"{row.guess} {symbols[row.color.lower()]}")
        if row.comment:
            st.write(f"Commentaire: {row.comment}")
        st.divider()
