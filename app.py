from flask import Flask, render_template, request, send_file, send_from_directory, after_this_request
import os, uuid, zipfile, shutil
from process_pdf import process_pdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def keep_latest_jobs(upload_base, output_base, keep=2):
    """
    Keep only latest `keep` jobs, delete older ones
    """
    # Collect jobs with timestamps
    jobs = []

    for job_id in os.listdir(output_base):
        job_path = os.path.join(output_base, job_id)
        if os.path.isdir(job_path):
            mtime = os.path.getmtime(job_path)
            jobs.append((mtime, job_id))

    # Sort newest first
    jobs.sort(reverse=True)

    # Jobs to delete
    old_jobs = jobs[keep:]

    for _, job_id in old_jobs:
        try:
            shutil.rmtree(os.path.join(output_base, job_id), ignore_errors=True)
            shutil.rmtree(os.path.join(upload_base, job_id), ignore_errors=True)
            zip_file = os.path.join(output_base, f"{job_id}.zip")
            if os.path.exists(zip_file):
                os.remove(zip_file)
            print(f"🧹 Deleted old job: {job_id}")
        except Exception as e:
            print("Cleanup error:", e)


# @app.route("/", methods=["GET", "POST"])
# def index():
#     if request.method == "POST":
#         pdfs = request.files.getlist("pdfs")
#         job_id = str(uuid.uuid4())

#         job_upload_dir = os.path.join(UPLOAD_DIR, job_id)
#         job_output_dir = os.path.join(OUTPUT_DIR, job_id)

#         os.makedirs(job_upload_dir, exist_ok=True)
#         os.makedirs(job_output_dir, exist_ok=True)

#         # ---- Queue processing (one-by-one) ----
#         for pdf in pdfs:
#             input_pdf = os.path.join(job_upload_dir, pdf.filename)
#             pdf.save(input_pdf)

#             out_dir = os.path.join(
#                 job_output_dir,
#                 os.path.splitext(pdf.filename)[0]
#             )
#             os.makedirs(out_dir, exist_ok=True)

#             process_pdf(input_pdf, out_dir)

#         return render_template("preview.html", job_id=job_id)

#     return render_template("index.html")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        # 🧹 Clean old jobs, keep only latest 2
        keep_latest_jobs(UPLOAD_DIR, OUTPUT_DIR, keep=2)

        pdfs = request.files.getlist("pdfs")
        job_id = str(uuid.uuid4())

        job_upload_dir = os.path.join(UPLOAD_DIR, job_id)
        job_output_dir = os.path.join(OUTPUT_DIR, job_id)

        os.makedirs(job_upload_dir, exist_ok=True)
        os.makedirs(job_output_dir, exist_ok=True)

        for pdf in pdfs:
            input_pdf = os.path.join(job_upload_dir, pdf.filename)
            pdf.save(input_pdf)

            out_dir = os.path.join(
                job_output_dir,
                os.path.splitext(pdf.filename)[0]
            )
            os.makedirs(out_dir, exist_ok=True)

            process_pdf(input_pdf, out_dir)

        return render_template("preview.html", job_id=job_id)

    return render_template("index.html")


@app.route("/preview/<job_id>")
def preview(job_id):
    base = os.path.join(OUTPUT_DIR, job_id)

    for pdf_folder in sorted(os.listdir(base)):
        folder = os.path.join(base, pdf_folder)
        files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
        if files:
            return send_from_directory(folder, files[0])

    return "No labels generated", 404


@app.route("/download/<job_id>")
def download(job_id):
    upload_folder = os.path.join(UPLOAD_DIR, job_id)
    output_folder = os.path.join(OUTPUT_DIR, job_id)
    zip_path = f"{output_folder}.zip"

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, _, files in os.walk(output_folder):
            for f in files:
                full = os.path.join(root, f)
                zipf.write(full, arcname=os.path.relpath(full, output_folder))

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(upload_folder)
            shutil.rmtree(output_folder)
            os.remove(zip_path)
        except:
            pass
        return response

    return send_file(zip_path, as_attachment=True)



@app.errorhandler(413)
def file_too_large(e):
    return "File too large. Max 10MB allowed.", 413

if __name__ == "__main__":
    app.run()
