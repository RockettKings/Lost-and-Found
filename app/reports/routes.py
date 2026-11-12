from flask import Blueprint

# Create reports Blueprint
reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

# Define routes
@reports_bp.route("/<int:report_id>", methods=["GET"])
def get_report(report_id):
    return