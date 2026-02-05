import requests
import streamlit as st

st.set_page_config(page_title="PA1 Client", layout="centered")
st.title("PA1 Client")

# If Ordering runs on the SAME VM, localhost:8080 is correct.
ORDERING_URL = st.text_input("Ordering base URL", value="http://localhost:8080")

def order_form(title, endpoint):
    st.subheader(title)
    request_id = st.text_input("request_id (customer_id or supplier_id)", key=f"{endpoint}-id")

    st.write("Items (qty must be > 0)")
    items = []
    for i in range(5):
        cols = st.columns(3)
        name = cols[0].text_input("name", key=f"{endpoint}-name-{i}")
        qty = cols[1].number_input("qty", min_value=0, step=1, key=f"{endpoint}-qty-{i}")
        category = cols[2].selectbox(
            "category", ["BREAD", "DAIRY", "MEAT", "PRODUCE", "PARTY"],
            key=f"{endpoint}-cat-{i}"
        )
        if name and qty > 0:
            items.append({"name": name, "qty": int(qty), "category": category})

    if st.button("Submit", key=f"{endpoint}-submit"):
        payload = {"request_id": request_id, "items": items}
        try:
            r = requests.post(f"{ORDERING_URL}{endpoint}", json=payload, timeout=10)
            st.json(r.json())
        except Exception as e:
            st.error(str(e))

tabs = st.tabs(["Grocery Order", "Restock Order"])
with tabs[0]:
    order_form("Grocery Order", "/grocery_order")
with tabs[1]:
    order_form("Restock Order", "/restock_order")
