import json
import os

from flask import Flask, abort, render_template, request, send_file

from backorder.config.configuration import Configuartion
from backorder.constant import CONFIG_DIR, get_current_time_stamp
from backorder.entity.backorder_predictor import backorderData, backorderPredictor
from backorder.logger import get_log_dataframe
from backorder.pipeline.pipeline import Pipeline
from backorder.util.util import read_yaml_file, write_yaml_file

ROOT_DIR = os.getcwd()
LOG_FOLDER_NAME = "logs"
PIPELINE_FOLDER_NAME = "backorder"
SAVED_MODELS_DIR_NAME = "saved_models"
MODEL_CONFIG_FILE_PATH = os.path.join(ROOT_DIR, CONFIG_DIR, "model.yaml")
LOG_DIR = os.path.join(ROOT_DIR, LOG_FOLDER_NAME)
PIPELINE_DIR = os.path.join(ROOT_DIR, PIPELINE_FOLDER_NAME)
MODEL_DIR = os.path.join(ROOT_DIR, SAVED_MODELS_DIR_NAME)
BACKORDER_DATA_KEY = "backorder_data"
WENT_ON_BACK_ORDER_KEY = "went_on_backorder"

app = application = Flask(__name__)


@app.route("/artifact", defaults={"req_path": "backorder"})
@app.route("/artifact/<path:req_path>")
def render_artifact_dir(req_path):
    os.makedirs("backorder", exist_ok=True)
    abs_path = os.path.join(req_path)

    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        if ".html" in abs_path:
            with open(abs_path, "r", encoding="utf-8") as file:
                content = ""
                for line in file.readlines():
                    content = f"{content}{line}"
                return content
        return send_file(abs_path)

    files = {
        os.path.join(abs_path, file_name): file_name
        for file_name in os.listdir(abs_path)
        if "artifact" in os.path.join(abs_path, file_name)
    }

    result = {
        "files": files,
        "parent_folder": os.path.dirname(abs_path),
        "parent_label": abs_path,
    }
    return render_template("files.html", result=result)


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/view_experiment_hist", methods=["GET", "POST"])
def view_experiment_history():
    experiment_df = Pipeline.get_experiments_status()
    context = {"experiment": experiment_df.to_html(classes="table table-striped col-12")}
    return render_template("experiment_history.html", context=context)


@app.route("/train", methods=["GET", "POST"])
def train():
    message = ""
    pipeline = Pipeline(config=Configuartion(current_time_stamp=get_current_time_stamp()))
    if not Pipeline.experiment.running_status:
        message = "Training started."
        pipeline.start()
    else:
        message = "Training is already in progress."
    context = {
        "experiment": pipeline.get_experiments_status().to_html(
            classes="table table-striped col-12"
        ),
        "message": message,
    }
    return render_template("train.html", context=context)


@app.route("/predict", methods=["GET", "POST"])
def predict():
    context = {BACKORDER_DATA_KEY: None, WENT_ON_BACK_ORDER_KEY: None}

    if request.method == "POST":
        national_inv = float(request.form["national_inv"])
        lead_time = float(request.form["lead_time"])
        in_transit_qty = float(request.form["in_transit_qty"])
        forecast_3_month = float(request.form["forecast_3_month"])
        forecast_6_month = float(request.form["forecast_6_month"])
        forecast_9_month = float(request.form["forecast_9_month"])
        sales_1_month = float(request.form["sales_1_month"])
        sales_3_month = float(request.form["sales_3_month"])
        sales_6_month = float(request.form["sales_6_month"])
        sales_9_month = float(request.form["sales_9_month"])
        min_bank = float(request.form["min_bank"])
        potential_issue = request.form["potential_issue"]
        pieces_past_due = float(request.form["pieces_past_due"])
        perf_6_month_avg = float(request.form["perf_6_month_avg"])
        perf_12_month_avg = float(request.form["perf_12_month_avg"])
        local_bo_qty = float(request.form["local_bo_qty"])
        deck_risk = request.form["deck_risk"]
        oe_constraint = request.form["oe_constraint"]
        ppap_risk = request.form["ppap_risk"]
        stop_auto_buy = request.form["stop_auto_buy"]
        rev_stop = request.form["rev_stop"]

        backorder_data = backorderData(
            national_inv=national_inv,
            lead_time=lead_time,
            in_transit_qty=in_transit_qty,
            forecast_3_month=forecast_3_month,
            forecast_6_month=forecast_6_month,
            forecast_9_month=forecast_9_month,
            sales_1_month=sales_1_month,
            sales_3_month=sales_3_month,
            sales_6_month=sales_6_month,
            sales_9_month=sales_9_month,
            min_bank=min_bank,
            potential_issue=potential_issue,
            pieces_past_due=pieces_past_due,
            perf_6_month_avg=perf_6_month_avg,
            perf_12_month_avg=perf_12_month_avg,
            local_bo_qty=local_bo_qty,
            deck_risk=deck_risk,
            oe_constraint=oe_constraint,
            ppap_risk=ppap_risk,
            stop_auto_buy=stop_auto_buy,
            rev_stop=rev_stop,
        )
        backorder_df = backorder_data.get_backorder_input_data_frame()
        backorder = backorderPredictor(model_dir=MODEL_DIR)
        went_on_backorder = backorder.predict(X=backorder_df)
        context = {
            BACKORDER_DATA_KEY: backorder_data.get_backorder_data_as_dict(),
            WENT_ON_BACK_ORDER_KEY: went_on_backorder,
        }
        return render_template("predict.html", context=context)

    return render_template("predict.html", context=context)


@app.route("/saved_models", defaults={"req_path": "saved_models"})
@app.route("/saved_models/<path:req_path>")
def saved_models_dir(req_path):
    os.makedirs("saved_models", exist_ok=True)
    abs_path = os.path.join(req_path)

    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        return send_file(abs_path)

    files = {os.path.join(abs_path, file): file for file in os.listdir(abs_path)}

    result = {
        "files": files,
        "parent_folder": os.path.dirname(abs_path),
        "parent_label": abs_path,
    }
    return render_template("saved_model_files.html", result=result)


@app.route("/update_model_config", methods=["GET", "POST"])
def update_model_config():
    if request.method == "POST":
        model_config = request.form["new_model_config"]
        model_config = model_config.replace("'", '"')
        model_config = json.loads(model_config)

        write_yaml_file(file_path=MODEL_CONFIG_FILE_PATH, data=model_config)

    model_config = read_yaml_file(file_path=MODEL_CONFIG_FILE_PATH)
    return render_template("update_model.html", result={"model_config": model_config})


@app.route("/logs", defaults={"req_path": f"{LOG_FOLDER_NAME}"})
@app.route("/{LOG_FOLDER_NAME}/<path:req_path>")
def render_log_dir(req_path):
    os.makedirs(LOG_FOLDER_NAME, exist_ok=True)
    abs_path = os.path.join(req_path)

    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        log_df = get_log_dataframe(abs_path)
        context = {"log": log_df.to_html(classes="table-striped", index=False)}
        return render_template("log.html", context=context)

    files = {os.path.join(abs_path, file): file for file in os.listdir(abs_path)}

    result = {
        "files": files,
        "parent_folder": os.path.dirname(abs_path),
        "parent_label": abs_path,
    }
    return render_template("log_files.html", result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
