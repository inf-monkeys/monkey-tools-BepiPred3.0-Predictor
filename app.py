import sys
from bp3 import bepipred3
from pathlib import Path
import uuid
import os
import re
from flask import Flask, request, jsonify
from flask_restx import Api, Resource
import traceback
from loguru import logger
from utils import s3_client, convert_csv_to_json, port

app = Flask(__name__)
api = Api(
    app,
    version="1.0",
    title="Monkey Tool BepiPred3.0 Predictor API",
    description="Monkey Tool BepiPred3.0 Predictor API, Based on https://github.com/UberClifford/BepiPred3.0-Predictors",
)
ns = api.namespace("", description="BepiPred3.0 Predictor API")


@app.before_request
def before_request():
    request.app_id = request.headers.get("x-monkeys-appid")
    request.user_id = request.headers.get("x-monkeys-userid")
    request.team_id = request.headers.get("x-monkeys-teamid")
    request.workflow_id = request.headers.get("x-monkeys-workflowid")
    request.workflow_instance_id = request.headers.get("x-monkeys-workflow-instanceid")


@app.errorhandler(Exception)
def handle_exception(error):
    traceback.print_exc()
    response = {"message": str(error)}
    response["code"] = 500
    return jsonify(response), response["code"]


aa3to1 = {
    "ALA": "A",
    "VAL": "V",
    "PHE": "F",
    "PRO": "P",
    "MET": "M",
    "ILE": "I",
    "LEU": "L",
    "ASP": "D",
    "GLU": "E",
    "LYS": "K",
    "ARG": "R",
    "SER": "S",
    "THR": "T",
    "TYR": "Y",
    "HIS": "H",
    "CYS": "C",
    "ASN": "N",
    "GLN": "Q",
    "TRP": "W",
    "GLY": "G",
    "MSE": "M",
}


def convert_pdb_to_fasta(pdb_file, fasta_file):
    ca_pattern = re.compile(
        "^ATOM\s{2,6}\d{1,5}\s{2}CA\s[\sA]([A-Z]{3})\s([\s\w])|^HETATM\s{0,4}\d{1,5}\s{2}CA\s[\sA](MSE)\s([\s\w])"
    )
    filename = os.path.basename(pdb_file).split(".")[0]
    chain_dict = dict()
    chain_list = []

    fp = open(pdb_file, "rU")
    for line in fp.read().splitlines():
        if line.startswith("ENDMDL"):
            break
        match_list = ca_pattern.findall(line)
        if match_list:
            resn = match_list[0][0] + match_list[0][2]
            chain = match_list[0][1] + match_list[0][3]
            if chain in chain_dict:
                chain_dict[chain] += aa3to1[resn]
            else:
                chain_dict[chain] = aa3to1[resn]
                chain_list.append(chain)
    fp.close()

    with open(fasta_file, "w") as f:
        for chain in chain_list:
            sys.stdout.write(">%s:%s\n%s\n" % (filename, chain, chain_dict[chain]))
            f.write(">%s:%s\n%s\n" % (filename, chain, chain_dict[chain]))


@app.get("/manifest.json")
def get_manifest():
    return {
        "schema_version": "v1",
        "display_name": "My Awesome Weather Tool",
        "namespace": "bepipred30_predictor",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "/swagger.json"},
        "contact_email": "dev@inf-monkeys.com",
    }


@ns.route("/bepipred30-predictor")
class Bepipred30PredictorResource(Resource):
    @ns.doc("bepipred30_predictor")
    @ns.vendor(
        {
            "x-monkey-tool-name": "bepipred30_predictor",
            "x-monkey-tool-categories": ["bio"],
            "x-monkey-tool-display-name": "免疫原性预测",
            "x-monkey-tool-description": "蛋白质的免疫原性预测",
            "x-monkey-tool-icon": "emoji:🧬:#f2c1be",
            "x-monkey-tool-input": [
                {
                    "displayName": "文件类型",
                    "name": "file_type",
                    "type": "options",
                    "default": "pdb",
                    "options": [
                        {
                            "name": "PDB",
                            "value": "pdb",
                        },
                        {
                            "name": "FASTA",
                            "value": "fasta",
                        },
                    ],
                    "required": True,
                },
                {
                    "displayName": "文件链接",
                    "name": "file_url",
                    "type": "file",
                    "required": True,
                    "typeOptions": {
                        "multipleValues": False,
                        "max": 1
                    }
                },
            ],
            "x-monkey-tool-output": [
                {
                    "name": "raw_output.csv",
                    "displayName": "原始 CSV 文件",
                    "type": "string",
                },
                {
                    "name": "json",
                    "displayName": "JSON 结果",
                    "type": "jsonObject",
                },
                {
                    "name": "bp3_linscore_bplots",
                    "displayName": "bp3_linscore_bplots",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "output_interactive_figures.html",
                            "displayName": "output_interactive_figures",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "bp3_score_bplots",
                    "displayName": "bp3_score_bplots",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "output_interactive_figures.html",
                            "displayName": "output_interactive_figures.html",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "mjv_voting",
                    "displayName": "mjv_voting",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_preds.fasta",
                            "displayName": "Bcell_epitope_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "mjv_voting",
                    "displayName": "mjv_voting",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_preds.fasta",
                            "displayName": "Bcell_epitope_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "top10",
                    "displayName": "top10",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_top_10pct_preds.fasta",
                            "displayName": "Bcell_epitope_top_10pct_preds.fasta",
                            "type": "string",
                        },
                        {
                            "name": "Bcell_linepitope_top_10pct_preds.fasta",
                            "displayName": "Bcell_linepitope_top_10pct_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "top30",
                    "displayName": "top30",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_top_30pct_preds.fasta",
                            "displayName": "Bcell_epitope_top_30pct_preds.fasta",
                            "type": "string",
                        },
                        {
                            "name": "Bcell_linepitope_top_30pct_preds.fasta",
                            "displayName": "Bcell_linepitope_top_30pct_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "top50",
                    "displayName": "top50",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_top_50pct_preds.fasta",
                            "displayName": "Bcell_epitope_top_50pct_preds.fasta",
                            "type": "string",
                        },
                        {
                            "name": "Bcell_linepitope_top_50pct_preds.fasta",
                            "displayName": "Bcell_linepitope_top_50pct_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "top70",
                    "displayName": "top70",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_top_70pct_preds.fasta",
                            "displayName": "Bcell_epitope_top_70pct_preds.fasta",
                            "type": "string",
                        },
                        {
                            "name": "Bcell_linepitope_top_70pct_preds.fasta",
                            "displayName": "Bcell_linepitope_top_70pct_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "top90",
                    "displayName": "top90",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_top_90pct_preds.fasta",
                            "displayName": "Bcell_epitope_top_90pct_preds.fasta",
                            "type": "string",
                        },
                        {
                            "name": "Bcell_linepitope_top_90pct_preds.fasta",
                            "displayName": "Bcell_linepitope_top_90pct_preds.fasta",
                            "type": "string",
                        },
                    ],
                },
                {
                    "name": "var_thresh",
                    "displayName": "var_thresh",
                    "type": "jsonObject",
                    "properties": [
                        {
                            "name": "Bcell_epitope_preds",
                            "displayName": "Bcell_epitope_preds",
                            "type": "string",
                        },
                    ],
                },
            ],
            "x-monkey-tool-extra": {
                "estimateTime": 30,
            },
        }
    )
    def post(self):
        file_type = request.json.get("file_type")
        file_url = request.json.get("file_url")
        if isinstance(file_url, list):
            file_url = file_url[0]
        logger.info(
            f"Start to run bepipred3.0 predictor: file_type={file_type}, file_url={file_url}"
        )
        input_file_name = s3_client.download_file(file_url)

        # 将 pdb 转换为 fasta
        if file_type == "pdb":
            logger.info("Input file is pdb, converting to fasta file")
            fasta_file = input_file_name.replace(".pdb", ".fasta")
            convert_pdb_to_fasta(input_file_name, fasta_file)
            input_file_name = fasta_file

        input_file_name = Path(input_file_name)

        MyAntigens = bepipred3.Antigens(
            input_file_name, Path.cwd() / "esm2_encodings", add_seq_len=True
        )

        MyBP3EnsemblePredict = bepipred3.BP3EnsemblePredict(MyAntigens)
        MyBP3EnsemblePredict.run_bp3_ensemble()
        out_dir = Path.cwd() / "output" / f"{uuid.uuid4()}"
        MyBP3EnsemblePredict.create_csvfile(out_dir)

        top_pcts = (0.1, 0.3, 0.5, 0.7, 0.9)
        for top_pct in top_pcts:
            MyBP3EnsemblePredict.top_pred_pct = top_pct
            pct_dir = out_dir / f"top{round(top_pct*100)}"
            MyBP3EnsemblePredict.create_toppct_files(pct_dir)
            for f in pct_dir.glob("*.fasta"):
                print(str(f))

        # majority vote prediction of BepiPred-3.0 models
        MyBP3EnsemblePredict.bp3_pred_majority_vote(out_dir / "mjv_voting")
        # variable threshold (BepiPred-3.0 score >= 0.2)
        MyBP3EnsemblePredict.bp3_pred_variable_threshold(
            out_dir / "var_thresh", var_threshold=0.2
        )

        # create figures with BepiPred-3.0 scoring
        MyBP3EnsemblePredict.bp3_generate_plots(
            out_dir / "bp3_score_bplots", num_interactive_figs=50
        )
        # create figures using rolling mean score (linear epitope scoring)
        MyBP3EnsemblePredict.bp3_generate_plots(
            out_dir / "bp3_linscore_bplots",
            num_interactive_figs=50,
            use_rolling_mean=True,
        )
        logger.info("Run bepipred3.0 predictor finished")
        result = s3_client.upload_directory(out_dir)
        logger.info("Upload result to oss finished")
        logger.info("Start to convert csv to json")

        csv_data = convert_csv_to_json(out_dir / "raw_output.csv")
        csv_data = [float(item.get("BepiPred-3.0 score")) for item in csv_data]
        result["json"] = csv_data

        return result


if __name__ == "__main__":
    logger.info(f"Start to run bepipred3.0 predictor, port={port}")
    app.run(host="0.0.0.0", port=port)
