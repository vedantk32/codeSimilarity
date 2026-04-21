import streamlit as st
import io
import tempfile
from pathlib import Path
import pandas as pd
import plotly.express as px
from copydetect import CodeFingerprint, compare_files
from copydetect.utils import highlight_overlap

# ------------------- Improved Code Extraction -------------------
def extract_code_from_file(uploaded_file):
    """Robust code extraction from PDF, DOCX, TXT, and code files."""
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
                    lines = page_text.split('\n')
                    for line in lines:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        # Much better heuristic for code in PDFs
                        if (any(kw in stripped for kw in ['public ', 'private ', 'class ', 'void ', 'int ', 
                                                         'String ', 'import ', 'System.', 'def ', 'function', 
                                                         '{', '}', '//', '/*', '#', 'selenium', 'driver', 'assert']) or
                            stripped[0].isspace() or len(stripped) > 30):   # long lines are likely code
                            text += line + '\n'
            Path(tmp_path).unlink(missing_ok=True)
            return text.strip()

        elif filename.endswith(('.docx', '.doc')):
            from docx import Document
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            doc = Document(tmp_path)
            text = "\n".join([para.text for para in doc.paragraphs 
                              if para.text.strip() and len(para.text.strip()) > 15])
            Path(tmp_path).unlink(missing_ok=True)
            return text.strip()

        else:
            # Plain text or code files
            return content.decode("utf-8", errors="ignore").strip()

    except Exception as e:
        st.warning(f"Extraction issue with {filename}: {str(e)[:100]}... Using raw text.")
        return content.decode("utf-8", errors="ignore").strip()


# ------------------- Streamlit App -------------------
st.set_page_config(page_title="Assignment Code Similarity Checker", page_icon="📋", layout="wide")

st.title("📋 Assignment Code Similarity Checker")
st.markdown("**For Teachers** • Upload multiple student submissions → Get similarity heatmap + detailed highlights")

uploaded_files = st.file_uploader(
    "Upload student assignments (PDF, DOCX, TXT, .py, .java, .cpp, .c, etc.)",
    type=None,
    accept_multiple_files=True,
    help="Supports PDF, Word documents, and code files. Code will be automatically extracted."
)

if uploaded_files and st.button("🚀 Analyze All Submissions", type="primary", use_container_width=True):
    if len(uploaded_files) < 2:
        st.error("Please upload at least 2 files.")
        st.stop()

    with st.spinner("Extracting code and computing similarities..."):
        student_codes = {}
        skipped = []

        for file in uploaded_files:
            code = extract_code_from_file(file)
            if code and len(code.strip()) > 50:   # Minimum meaningful code length
                student_codes[file.name] = code
            else:
                skipped.append(file.name)

        if skipped:
            st.warning(f"Skipped {len(skipped)} file(s) with insufficient code: {', '.join(skipped[:3])}")

        if len(student_codes) < 2:
            st.error("Not enough valid code could be extracted. Please try uploading files that contain actual source code.")
            st.info("Tip: For PDFs, make sure the code is selectable text (not scanned images).")
            st.stop()

        names = list(student_codes.keys())

        # Compute similarities
        similarity_matrix = pd.DataFrame(0.0, index=names, columns=names)
        results = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                name1, name2 = names[i], names[j]
                code1, code2 = student_codes[name1], student_codes[name2]

                try:
                    fp1 = CodeFingerprint(file=name1, k=25, win_size=1, fp=io.StringIO(code1))
                    fp2 = CodeFingerprint(file=name2, k=25, win_size=1, fp=io.StringIO(code2))

                    token_overlap, sims, slices = compare_files(fp1, fp2)
                    sim_score = max(sims[0], sims[1])

                    similarity_matrix.loc[name1, name2] = sim_score
                    similarity_matrix.loc[name2, name1] = sim_score

                    flag = "🔴 High" if sim_score >= 0.60 else "🟡 Medium" if sim_score >= 0.40 else "🟢 Low"

                    results.append({
                        "Student 1": name1,
                        "Student 2": name2,
                        "Similarity": f"{sim_score:.1%}",
                        "Flag": flag,
                        "Overlapping Tokens": token_overlap
                    })
                except Exception as e:
                    st.warning(f"Comparison failed for {name1} vs {name2}")

        # Results
        st.subheader("🔥 Similarity Heatmap")
        fig = px.imshow(similarity_matrix.values, x=names, y=names, text_auto=".0%",
                        color_continuous_scale="RdYlGn_r", aspect="auto")
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📊 Pairwise Results")
        if results:
            df = pd.DataFrame(results).sort_values("Similarity", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No significant similarities found.")

        # Detailed comparison
        st.subheader("🔍 Detailed Highlighted Comparison")
        col1, col2 = st.columns(2)
        with col1:
            stud1 = st.selectbox("Select First Student", names, key="stud1")
        with col2:
            stud2 = st.selectbox("Select Second Student", [n for n in names if n != stud1], key="stud2")

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
                        st.markdown(f"**{stud1}**")
                        st.code(hl1, language=Path(stud1).suffix.lstrip(".") or "java")
                    with c2:
                        st.markdown(f"**{stud2}**")
                        st.code(hl2, language=Path(stud2).suffix.lstrip(".") or "java")
                else:
                    st.info("No overlapping sections found for this pair.")
            except Exception as e:
                st.error(f"Error: {e}")

st.divider()
st.caption("Built for teachers • Smart code extraction from PDFs & documents")
