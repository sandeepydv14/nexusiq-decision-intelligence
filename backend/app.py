from flask import Flask, jsonify
from flask_cors import CORS

from config import MAX_UPLOAD_MB, ensure_directories
from database.db import init_db
from routes.analysis_routes import analysis_bp
from routes.cleaning_routes import cleaning_bp
from routes.dataset_routes import dataset_bp
from routes.ml_routes import ml_bp
from routes.query_routes import query_bp
from routes.report_routes import report_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    ensure_directories()
    init_db()

    app.register_blueprint(dataset_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(cleaning_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(report_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "Autonomous Data Analysis & Decision Intelligence Platform"})

    @app.errorhandler(413)
    def file_too_large(_err):
        return jsonify({"error": f"Uploaded file exceeds maximum allowed size of {MAX_UPLOAD_MB} MB."}), 413

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, debug=False)
