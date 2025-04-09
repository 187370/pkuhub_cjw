from flask import Blueprint, send_from_directory
import os

utils_bp = Blueprint('utils', __name__)

@utils_bp.route('/<path:filename>')
def serve_file(filename):
    utils_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils')
    return send_from_directory(utils_dir, filename)