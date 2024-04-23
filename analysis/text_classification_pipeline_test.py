from prefect import flow, task
from upload_data import * 
from datasets import load_dataset
from datetime import datetime
import s3fs
import pandas as pd
from utils import * 
from pyspark.sql import SparkSession
from transformers import pipeline
from pyspark.sql.functions import pandas_udf
from pyspark.sql.functions import lit, col
import argparse
from prometheus_client import start_http_server, Counter

iterations = Counter('pipeline_iterations', 'Number of experiments executed')

@task(retries=3, retry_delay_seconds=5, log_prints=True)
def upload_dataset_to_s3(dataset_name: str) -> str:
    """
    Loads a specified dataset, extracts the 'test' part, converts it to a Pandas DataFrame, and uploads it to S3.

    Args:
        dataset_name (str): The name of the dataset to load.

    Returns:
        str: The full S3 path where the dataset was saved.
    """
    dataset = load_dataset(dataset_name)
    dataset_keys = ['test']
    dfs = []
    for key in dataset_keys:
        df = dataset[key].to_pandas()['text'].to_frame()
        dfs.append(df)
    
    df = pd.concat(dfs, axis = 0)
    run_id = datetime.now().strftime('%Y%m%d%H%M%S')
    name = run_id + '_' + dataset_name + '.csv'
    full_name = f's3://comp0239-ucabryo/test-data/{name}'
    print(f'Saving: {full_name}')

    df.to_csv(full_name, index = None)
    return full_name
          
@task
def text_analysis(name: str, spark: SparkSession) -> str:
    """
    Loads a dataset from S3, performs text classification using a BERT model, and saves the results back to S3.

    Args:
        name (str): S3 path of the CSV file to analyze.
        spark (SparkSession): Active Spark session.

    Returns:
        str: The S3 folder path where the analysis results are stored.
    """
    classifier = pipeline(task="text-classification", model="philschmid/tiny-bert-sst2-distilled", truncation=True, top_k=None)
    
    @pandas_udf('string')
    def predict_udf(texts: pd.Series) -> pd.Series:
        prediction = [result[0]['label'] for result in classifier(texts.to_list(), batch_size=1)]
        return pd.Series(prediction)
        
    df = spark.read.csv(name, header = True)
    df = df.withColumn("label", predict_udf(col("text")))

    # Extract the job_id from the data_path
    job_id = name.split('/')[-1].split('_')[0]
    df = df.withColumn("jobid", lit(job_id))
    
    s3_folder = f"s3a://comp0239-ucabryo/spark-result/{job_id}/"
    df.write.csv(s3_folder, mode="overwrite")
    return job_id
    
@task(retries=3, retry_delay_seconds=5,log_prints=True)
def push_s3_sql(job_id: str, db: bool = False):
    """
    Collects all partial results from S3, merges them, and pushes a combined CSV back to S3.
    Optionally, data can also be pushed to a SQL database.

    Args:
        job_id (str): Identifier for the job whose results are to be processed.
        db (bool, optional): Whether to push results to SQL database. Defaults to False.
    """
    fs = s3fs.S3FileSystem(anon=False)  
    bucket_name = "comp0239-ucabryo"
    prefix = f"spark-result/{job_id}/"
    s3_directory = f"{bucket_name}/{prefix}"
    data_list = fs.glob(f"{s3_directory}part-*")
    
    dfs = []  # Use a list to collect DataFrames
    
    for file in data_list:
        file_path = f"s3://{file}"
        df_part = pd.read_csv(file_path,
                          names=["text", "label", "jobid"], 
                            header=None, 
                            escapechar="\\", 
                            quotechar='"',
                            dtype={"text": str, "label": str, "jobid": str})
        dfs.append(df_part)  
        fs.rm(file)
        
    print('Read all the partitions!')
    df = pd.concat(dfs, axis=0)  
    
    # Ensure s3fs is installed to use "s3://" schema
    df.to_csv(f"s3://comp0239-ucabryo/result/{job_id}.csv", index=False)
    print("Successfully push to s3!")
    
    if db:
        engine = postgres_connection('coursework')
        # df.rename(columns={'prediction': 'label'}, inplace=True)
        df.to_sql('prediction', con = engine.connect(), if_exists='append', index = False)
        print("Successfully push to sql db!")
    
@flow(retries=3, retry_delay_seconds=5, log_prints=True)
def full_pipeline(name: str, spark_session: SparkSession):
    """
    Executes the full data processing pipeline from dataset uploading, text analysis to storage.

    Args:
        name (str): Dataset name.
        spark_session (SparkSession): Spark session instance.
    """
    path = upload_dataset_to_s3(name)
    path = path.replace("s3://", "s3a://")
    jobid = text_analysis(path, spark_session)
    push_s3_sql(jobid)
    
if __name__ == '__main__':
    spark = SparkSession.builder \
        .master("spark://10.0.9.154:7077") \
        .appName("Text classification pipeline test") \
        .config("spark.executor.memory", "1536m") \
        .config("spark.python.worker.memory", "1536m") \
        .config("spark.hadoop.fs.s3a.bucket.all.committer.magic.enabled", "true") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk:1.12.262,org.apache.spark:spark-hadoop-cloud_2.12:3.3.1") \
        .getOrCreate()
    
    start_http_server(4506)
    
    parser = argparse.ArgumentParser(description='Upload dataset to S3.')
    parser.add_argument('dataset_name', type=str, help='Name of the dataset to upload')
    args = parser.parse_args()
    
    # run for 360 times
    for _ in range(360):
        full_pipeline(args.dataset_name, spark)
        iterations.inc()
        
    spark.stop()