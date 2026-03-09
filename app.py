import streamlit as st
import pandas as pd

st.title("CPQ — Project List")

if "projects" not in st.session_state:
    st.session_state.projects = []

st.subheader("Register New Project")
name  = st.text_input("Project Name")
start = st.text_input("Start Date (DD/MM/YYYY)")
end   = st.text_input("End Date (DD/MM/YYYY)")
value = st.number_input("Value (R$)", min_value=0.0, format="%.2f")

if st.button("Add Project"):
    if name == "" or start == "" or end == "":
        st.warning("⚠️ Please fill in all fields.")
    else:
        st.session_state.projects.append({
            "Name":       name,
            "Start Date": start,
            "End Date":   end,
            "Value":      value
        })
        st.success(f"✅ Project '{name}' added!")

if len(st.session_state.projects) > 0:
    st.subheader("Project List")
    df = pd.DataFrame(st.session_state.projects)
    df.index = range(1, len(df) + 1)
    df["Value"] = df["Value"].apply(lambda x: f"R$ {x:,.2f}")
    st.dataframe(df, use_container_width=True)
