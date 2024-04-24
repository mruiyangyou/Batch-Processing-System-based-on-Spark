# Batch Processing System for Sentimental analysis

## Structure 

* [database notebooks](./notebook/check_db.ipynb): contain removing, creating and inserting the table mentioned for further analysis in the report
* [app.py](./app.py): streamlit application
* [text_classification_pipeline.py](./text_classification_pipeline.py): main batch text classification pipeline based on spark
* [text_classification_pipeline_test.py](./text_classification_pipeline_test.py): batch job last for 24 hours (pipeline reliability 24-hour test)
* [utils.py](./utils.py): database utils functions for connection 



## Getting Started

You can access the app by [Sentimental analysis by spark](http://18.171.239.205:4200/)
## Run the app built by `Streamlit` to interact with the service

Connect to the client machine
```bash
ssh -i ~/.ssh/comp0239_key ec2-user@ec2-18-130-16-27.eu-west-2.compute.amazonaws.com
```

Run the app
```bash
git clone https://github.com/mruiyangyou/Batch-Processing-System-based-on-Spark.git
cd Batch-Processing-System-based-on-Spark/analysis

streamlit run app.py --server.port 4200
```

## Run the reliability 24-hour test for testing the pipeline

The test is carried out by running the batch analysis job on the huggingface data set [imdb](https://huggingface.co/datasets/stanfordnlp/imdb) 360 times with no interruption.
```bash
python text_classification_pipeline_test.py "imdb"
```
You can go to [Prefect UI](http://18.130.16.27:4200/dashboard) to monitor the pipeline.

