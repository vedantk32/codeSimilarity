import streamlit as st
import io
import tempfile
from pathlib import Path
import pandas as pd
import plotly.express as px
from copydetect import CodeFingerprint, compare_files
from copydetect.utils import highlight_overlap

# ------------------- Code Extraction Helpers -------------------
def extract_code_from_file(uploaded_file):
    """Extract only code blocks from PDF, DOCX, TXT, or code files. Ignores theory text."""
    filename = uploaded_file.name.lower()
    content = uploaded_file.read()

    try:
        if filename.endswith('.pdf'):
            import pdfplumber
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            text = ""
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    code_lines = [line for line in page_text.split('\n')
                                  if line.strip() and (line.strip()[0].isspace() or
                                      any(k in line for k in ['def ', 'int ', 'public ', '{', '}', 'import ', 
                                                              'print', '//', '/*', '#', 'class ']))]
                    text += '\n'.join(code_lines) + '\n'
            Path(tmp_path).unlink(missing_ok=True)
            return text.strip()

        elif filename.endswith(('.docx', '.doc')):
            from docx import Document
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            doc = Document(tmp_path)
            text = "\n".join([para.text for para in doc.paragraphs
                              if any(k in para.text for k in ['def ', '{', '}', 'import ', 'class ', '#', '//'])])
            Path(tmp_path).unlink(missing_ok=True)
            return text.strip()

        else:
            # Direct code files or TXT
            return content.decode("utf-8", errors="ignore").strip()

    except Exception as e:
        st.warning(f"Could not fully extract code from {filename}. Using raw text.")
        return content.decode("utf-8", errors="ignore").strip()


# ------------------- Streamlit App -------------------
st.set_page_config(page_title="Assignment Code Checker", page_icon="📋", layout="wide")

st.title("📋 Assignment Code Similarity Checker")
st.markdown("**For Teachers** • Upload multiple student submissions → Get similarity heatmap + detailed highlights")

# File uploader - multiple files (clean label, no size mention)
uploaded_files = st.file_uploader(
    "Upload student assignments (PDF, DOCX, TXT, .py, .java, .cpp, .c, etc.)",
    type=None,
    accept_multiple_files=True,
    help="You can upload multiple files at once. Code will be automatically extracted from PDFs and Word files."
)

if uploaded_files and st.button("🚀 Analyze All Submissions", type="primary", use_container_width=True):
    if len(uploaded_files) < 2:
        st.error("Please upload at least 2 files for comparison.")
        st.stop()

    with st.spinner("Extracting code and computing similarities..."):
        # Extract code from each file
        student_codes = {}
        for file in uploaded_files:
            code = extract_code_from_file(file)
            if code.strip():
                student_codes[file.name] = code
            else:
                st.warning(f"Skipped empty file: {file.name}")

        if len(student_codes) < 2:
            st.error("Not enough valid code extracted from the uploaded files.")
            st.stop()

        names = list(student_codes.keys())
        n = len(names)

        # Compute pairwise similarities using copydetect (quietly)
        similarity_matrix = pd.DataFrame(0.0, index=names, columns=names)
        results = []

        for i in range(n):
            for j in range(i + 1, n):
                name1, name2 = names[i], names[j]
                code1, code2 = student_codes[name1], student_codes[name2]

                try:
                    fp1 = CodeFingerprint(file=name1, k=25, win_size=1, fp=io.StringIO(code1))
                    fp2 = CodeFingerprint(file=name2, k=25, win_size=1, fp=io.StringIO(code2))

                    token_overlap, sims, slices = compare_files(fp1, fp2)
                    sim_score = max(sims[0], sims[1])  # symmetric

                    similarity_matrix.loc[name1, name2] = sim_score
                    similarity_matrix.loc[name2, name1] = sim_score

                    if sim_score >= 0.60:
                        flag = "🔴 High"
                    elif sim_score >= 0.40:
                        flag = "🟡 Medium"
                    else:
                        flag = "🟢 Low"

                    results.append({
                        "Student 1": name1,
                        "Student 2": name2,
                        "Similarity": f"{sim_score:.1%}",
                        "Flag": flag,
                        "Overlapping Tokens": token_overlap
                    })
                except:
                    pass  # Skip problematic pairs

        # Display Heatmap
        st.subheader("🔥 Similarity Heatmap")
        fig = px.imshow(
            similarity_matrix.values,
            x=names,
            y=names,
            text_auto=".0%",
            color_continuous_scale="RdYlGn_r",
            aspect="auto"
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

        # Results Table
        st.subheader("📊 Pairwise Results")
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values("Similarity", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No significant similarities found.")

        # Detailed view for selected pair
        st.subheader("🔍 Detailed Highlighted Comparison")
        col_a, col_b = st.columns(2)
        with col_a:
            stud1 = st.selectbox("Select First Student", names, key="s1")
        with col_b:
            stud2 = st.selectbox("Select Second Student", [n for n in names if n != stud1], key="s2")

        if st.button("Show Highlighted Similar Sections", use_container_width=True):
            try:
                code1 = student_codes[stud1]
                code2 = student_codes[stud2]
                fp1 = CodeFingerprint(file=stud1, k=25, win_size=1, fp=io.StringIO(code1))
                fp2 = CodeFingerprint(file=stud2, k=25, win_size=1, fp=io.StringIO(code2))
                _, _, slices = compare_files(fp1, fp2)

                if len(slices[0]) > 0:
                    hl1, _ = highlight_overlap(fp1.raw_code, slices[0],
                                               left_hl=">>> SIMILAR START <<<\n",
                                               right_hl="\n>>> SIMILAR END <<<")
                    hl2, _ = highlight_overlap(fp2.raw_code, slices[1],
                                               left_hl=">>> SIMILAR START <<<\n",
                                               right_hl="\n>>> SIMILAR END <<<")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**{stud1}** (highlighted)")
                        st.code(hl1, language=Path(stud1).suffix.lstrip(".") or None)
                    with c2:
                        st.markdown(f"**{stud2}** (highlighted)")
                        st.code(hl2, language=Path(stud2).suffix.lstrip(".") or None)
                else:
                    st.info("No overlapping sections detected for this pair.")
            except Exception as e:
                st.error(f"Error showing details: {e}")

st.divider()
st.caption("Built for teachers • Intelligent code extraction from PDFs & documents • Powered quietly by advanced fingerprinting")
