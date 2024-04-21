import streamlit as st 
import subprocess
from datetime import datetime
import pandas as pd
from st_files_connection import FilesConnection
from typing import Tuple, Optional

# set the title
st.title("Text Classification Service")

# set user option
option =  st.radio('Choose data input method:', ('Upload CSV File', 'Use Hugging Face Dataset'))

# Initialize variables to ensure they are defined outside of the conditional blocks
uploaded_file = None
dataset_name = ""
df = None  
conn = st.connection('s3', type=FilesConnection)

# when user choose to upload its own file
if option == 'Upload CSV File':
    uploaded_file = st.file_uploader("Choose a file", type = ['csv'])
    
    # perform check for the uploading files
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            if len(df.columns) != 1:
                st.error("The upload csv should had just one text column!")
                
            st.write(df.head(10))
        except Exception as e:
            st.error(e)
            
# when user choose to use data from huggingface
elif option == 'Use Hugging Face Dataset':
    dataset_name = st.text_input('Enter the Hugging Face dataset name:', placeholder='imdb')

def hf_text_classification_pipeline(run_id: str, dataset_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Runs a text classification pipeline using a specified dataset from Hugging Face.

    Args:
        run_id (str): Unique identifier for the run.
        dataset_name (str): Name of the dataset on the Hugging Face website.

    Returns:
        Tuple[Optional[str], Optional[str]]: A tuple containing the stdout if successful, or None and stderr if an error occurs.
    """
    try:
        command = ["python", "text_classification_pipeline.py", "hf", run_id, dataset_name]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr

def own_text_classification_pipeline(run_id: str, path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Runs a text classification pipeline using a local dataset.

    Args:
        run_id (str): Unique identifier for the run.
        path (str): File path to the local dataset.

    Returns:
        Tuple[Optional[str], Optional[str]]: A tuple containing the stdout if successful, or None and stderr if an error occurs.
    """
    try:
        command = ["python", "text_classification_pipeline.py", "own", run_id, path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr
    
@st.cache_data
def convert_df(df):
    return df.to_csv().encode('utf-8')

# when the submit button is pressed
if st.button('Submit'):
    if option == 'Upload CSV File' and uploaded_file is None:
        st.error('Please upload a file.')
    elif option == 'Use Hugging Face Dataset' and not dataset_name:
        st.error('Please enter a dataset name.')
    else:
        status_text = st.empty()
        status_text.text('Starting the pipeline...')
        spark_ui_link = 'http://localhost:8080' # Placeholder URL
        prefect_ui_link = 'http://18.130.16.27:4200' # Placeholder URL
        
        st.success('Processing started!')
        st.markdown(f'**Spark Master UI:** [Link]({spark_ui_link})')
        st.markdown(f'**Prefect UI:** [Link]({prefect_ui_link})')
        run_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        if dataset_name:
            output, error = hf_text_classification_pipeline(run_id, dataset_name)
            if error:
                st.error(f'Error during processing: {error}')
            else:
                st.divider()
                status_text.text('Processing successfully completed!')
                st.success('Processing successfully!')
                result = conn.read(f"comp0239-ucabryo/result/{run_id}.csv")
                
                csv = convert_df(result)

                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name='output.csv',
                    mime='text/csv',
                )
        
        file_path = f"s3://comp0239-ucabryo/test-data/{run_id}_test.csv"
        if option == 'Upload CSV File' and df is not None:
            df.to_csv(file_path, index = None)
            output, error = own_text_classification_pipeline(run_id, file_path)
            st.write(f"Upload to :{file_path}")
            if error:
                st.error(f'Error during processing: {error}')
            else:
                st.divider()
                status_text.text('Processing successfully completed!')
                st.success('Processing successfully!')
                result = conn.read(f"comp0239-ucabryo/result/{run_id}.csv")
                
                csv = convert_df(result)

                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name='output.csv',
                    mime='text/csv',
                )
                                
        

