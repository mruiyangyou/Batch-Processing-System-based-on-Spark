# Batch Processing System for Sentimental analysis

You can access the front end by [Sentimental analysis by spark](http://18.171.239.205:4200/)
## Run the front end built by `Streamlit` to interact with the service

Connect to the client machine
```bash
ssh -i ~/.ssh/comp0239_key ec2-user@ec2-18-130-16-27.eu-west-2.compute.amazonaws.com
```

Run the app
```bash
git clone 
cd analysis

streamlit run app.py
```

## Run the reliability 24-hour test for testing the pipeline

The test is carried out by running the batch analysis job on the huggingface data set [imdb](https://huggingface.co/datasets/stanfordnlp/imdb) 360 times with no interruption.
```bash
python text_classification_pipeline_test.py "imdb"
```
You can go to [Prefect UI](http://18.130.16.27:4200/dashboard) to monitor the pipeline.