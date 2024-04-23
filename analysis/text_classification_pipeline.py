from prefect import flow, task, get_run_logger
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


@task(log_prints=True)
def upload_dataset_to_s3(source: str, id: str, **kwargs) -> str:
    """
    Uploads a dataset to S3, supporting both Hugging Face datasets and user-provided files.
    
    Args:
        source (str): Source type ('hf' for Hugging Face, 'own' for own file).
        id (str): Unique identifier used to name the output file.
        **kwargs:
            dataset_name (str): Required if source is 'hf'. Name of the dataset on Hugging Face.
            file_path (str): Required if source is 'own'. Path to the user's file.

    Returns:
        str: The full S3 path where the file has been saved.

    Raises:
        ValueError: If required kwargs are missing based on the source type.
    """
    if source == 'hf':
        dataset_name = kwargs.get('dataset_name')
        if dataset_name is None:
            raise ValueError("dataset_name is required for huggingface source")
        dataset = load_dataset(dataset_name)
        dataset_keys = list(dataset.keys())
        # dataset_keys = ['test']
        dfs = []
        for key in dataset_keys:
            df = dataset[key].to_pandas()['text'].to_frame()
            dfs.append(df)
        
        df = pd.concat(dfs, axis = 0)
        # run_id = datetime.now().strftime('%Y%m%d%H%M%S')
        run_id = id
        name = run_id + '_' + dataset_name + '.csv'
        s3_path = f's3://comp0239-ucabryo/test-data/{name}'
        print(f'Saving: {s3_path}')

        df.to_csv(s3_path, index = None)
    elif source == 'own':
        # full_name = kwargs.get('file_path')
        # if full_name is None:
        #     raise ValueError("file_path is required for upload your own data!")
        original_path = kwargs.get('file_path')
        if original_path is None:
            raise ValueError("file_path is required for upload your own data!")
        df = pd.read_csv(original_path)
        df.dropna(inplace=True)
        s3_path = original_path.replace('streamlit-data', 'test-data')
        df.to_csv(s3_path, index = None)
        # fs.copy(original_path, new_path)
        print(f"File copied from {original_path} to {s3_path}")
    return s3_path
          
@task
def text_analysis(name: str, spark: SparkSession):
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
    
@flow(log_prints=True)
def full_pipeline(source: str, id: str, spark_session: SparkSession, **kwargs):
    """
    Orchestrates a complete data processing pipeline from data upload to analysis and storage.

    Args:
        source (str): Source type ('hf' for Hugging Face, 'own' for own file).
        id (str): Unique identifier for this run, used in naming outputs.
        spark_session (SparkSession): Spark session for processing data.
        **kwargs: Additional keyword arguments for specifying dataset details or file paths.

    Raises:
        Exception: Propagates exceptions from each step with appropriate logging.
    """
    logger = get_run_logger()
    try:
        path = upload_dataset_to_s3(source, id, **kwargs)
        path = path.replace("s3://", "s3a://")
    except Exception as e:
        # Log the error and potentially stop the pipeline or take corrective action
        logger.error(f"Failed to upload dataset to S3. Error: {e}")
        raise
    
    # If the upload succeeds, proceed with text analysis
    try:
        jobid = text_analysis(path, spark_session)
    except Exception as e:
        logger.error(f"Text analysis failed. Error: {e}")
        raise
    
    # Assuming text analysis succeeds, push results to S3 and optionally SQL
    try:
        push_s3_sql(jobid, bool = True)
    except Exception as e:
        logger.error(f"Failed to push results to S3/SQL. Error: {e}")
        raise

    # If the pipeline reaches this point, all steps have succeeded
    logger.info("Pipeline completed successfully.")
    
if __name__ == '__main__':
    spark = SparkSession.builder \
        .master("spark://10.0.9.154:7077") \
        .appName("Text classification pipeline test") \
        .config("spark.executor.memory", "1536m") \
        .config("spark.python.worker.memory", "1536m") \
        .config("spark.hadoop.fs.s3a.bucket.all.committer.magic.enabled", "true") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk:1.12.262,org.apache.spark:spark-hadoop-cloud_2.12:3.3.1") \
        .getOrCreate()
    
    parser = argparse.ArgumentParser(description='Upload dataset to S3.')
    parser.add_argument('source', choices=['own', 'hf'], help='The source of the data: "own" for user-uploaded data, or "hugging_face" for Hugging Face datasets.')
    parser.add_argument('id', type = str, help = 'id of your task')
    parser.add_argument('dataset', type=str, help='Name of the dataset to upload')
    args = parser.parse_args()
    dataset = args.dataset
    source =  args.source
    id = args.id 
    
    try:
        if source == 'own':
            full_pipeline(source, id, spark, file_path = dataset)
        elif source == 'hf':
            full_pipeline(source, id, spark, dataset_name = dataset)
        else:
            raise ValueError(f'Source should either be own or hf, instead your souce: {source}')
    finally:
        spark.stop()