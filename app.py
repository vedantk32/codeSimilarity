import streamlit as st
import io
from pathlib import Path

# Internal similarity engine (powered quietly)
from copydetect import CodeFingerprint, compare_files
from copydetect.utils import highlight_overlap

st.set_page_config(
    page_title="Code Similarity Checker",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Code Similarity Checker")
st.markdown("""
A smart tool that analyzes the **logical structure** of two code pieces and highlights similar sections.  
It focuses on core logic while being robust to changes in variable names, comments, formatting, and whitespace.
""")

# Sidebar – neutral settings
with st.sidebar:
    st.header("⚙️ Analysis Settings")
    k_value = st.slider("Detection Precision", min_value=5, max_value=50, value=25,
                        help="Higher value makes detection more precise (fewer false matches)")
    window = st.slider("Analysis Window", min_value=1, max_value=10, value=1)
    st.caption("Adjust for your use case — higher precision reduces noise.")

# Two-column input
col1, col2 = st.columns(2)

with col1:
    st.subheader("First Code / File")
    uploaded1 = st.file_uploader("Upload file", type=None, key="up1")
    if uploaded1:
        code1 = uploaded1.getvalue().decode("utf-8", errors="ignore")
        filename1 = uploaded1.name
        st.caption(f"📄 {filename1} • {len(code1):,} characters")
    else:
        filename1 = st.text_input("Filename for syntax highlighting", "file1.py", key="fn1")
        code1 = st.text_area("Paste your first code here", height=420, key="c1")

with col2:
    st.subheader("Second Code / File")
    uploaded2 = st.file_uploader("Upload file", type=None, key="up2")
    if uploaded2:
        code2 = uploaded2.getvalue().decode("utf-8", errors="ignore")
        filename2 = uploaded2.name
        st.caption(f"📄 {filename2} • {len(code2):,} characters")
    else:
        filename2 = st.text_input("Filename for syntax highlighting", "file2.py", key="fn2")
        code2 = st.text_area("Paste your second code here", height=420, key="c2")

if st.button("🔍 Run Similarity Analysis", type="primary", use_container_width=True):
    if not (code1.strip() and code2.strip()):
        st.error("Please provide code in both sections.")
        st.stop()

    with st.spinner("Analyzing logical structure..."):
        try:
            # Quiet internal processing
            fp1 = CodeFingerprint(
                file=filename1,
                k=k_value,
                win_size=window,
                fp=io.StringIO(code1),
                filter=True
            )
            fp2 = CodeFingerprint(
                file=filename2,
                k=k_value,
                win_size=window,
                fp=io.StringIO(code2),
                filter=True
            )

            token_overlap, similarities, overlap_slices = compare_files(fp1, fp2)

            st.success("✅ Analysis complete!")

            # Results metrics
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Similar Tokens Detected", f"{token_overlap:,}")
            with m2:
                st.metric("Similarity Score (First → Second)", f"{similarities[0]:.1%}")
            with m3:
                st.metric("Similarity Score (Second → First)", f"{similarities[1]:.1%}")

            # Highlighted similar sections
            if token_overlap > 0 and len(overlap_slices[0]) > 0:
                st.subheader("📍 Similar Sections Highlighted")

                hl1, _ = highlight_overlap(
                    fp1.raw_code, overlap_slices[0],
                    left_hl=">>> SIMILAR START <<<\n",
                    right_hl="\n>>> SIMILAR END <<<"
                )
                hl2, _ = highlight_overlap(
                    fp2.raw_code, overlap_slices[1],
                    left_hl=">>> SIMILAR START <<<\n",
                    right_hl="\n>>> SIMILAR END <<<"
                )

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**First Code** (similar parts marked)")
                    st.code(hl1, language=Path(filename1).suffix.lstrip(".") or None)
                with c2:
                    st.markdown("**Second Code** (similar parts marked)")
                    st.code(hl2, language=Path(filename2).suffix.lstrip(".") or None)
            else:
                st.info("No significant structural similarity detected above the current threshold.")

            st.caption("The tool emphasizes logical patterns over exact text matching.")

        except Exception as e:
            st.error(f"Analysis error: {str(e)}")
            st.info("Try shorter code snippets or adjust the precision slider.")

st.divider()
st.markdown("Built by **Vedant** • Ready for Streamlit Cloud or Hugging Face Spaces")
