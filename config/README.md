# Set up a spark cluster based on ec2 machines from scratch

This section contains all the infrastrucutre as code notebooks by **ansible** to set up a spark cluster with six ec2 machines from scratch. Before start, please have a secret key to access the six ec2 machines, e.g `comp0239_key`. You can recreate my spark cluster settings and my enviroment for running **text classification analysis**:

```bash
git clone https://github.com/mruiyangyou/COMP0239-Coursework.git
cd COMP0239-Coursework/config
ansible-playbook -i inventory.ini configure_machines.yml --private-key=~/.ssh/comp0239_key
ansible-playbook -i inventory.ini deploy_services.yml --private-key=~/.ssh/comp0239_key
```

As the port 8080 is not open for all ip address under our security group, you need to perform ssh tunel on the host machine before access the spark UI

```bash
ssh -i ~/.ssh/comp0239_key -L 8080:localhost:8080 ec2-user@ec2-18-171-62-1.eu-west-2.compute.amazonaws.com -o ServerAliveInterval=60 -o ServerAliveCountMax=2
```

Then if everything went smoothly, you can visit the spark UI, prefect UI and Grafana by [Spark Master UI](http://localhost:8080), [Prefect Server UI](http://18.130.16.27:4200), [Grafana UI](http://18.130.16.27:3000).

## Comments for each notebook

### `configure_machines.yml`

- configure working machines

  - [attach_storage](./roles/attach_storage/tasks/main.yml): attach addtional ebs to spark working machines
  - [configure_worker](./roles/configure_worker/tasks/main.yml): install relevant python packages to do the analysis task

- install pyspark and prefect on the client machine as a spark driver

  - install pyspark and prefect on the client machines which is a spark driver

- configure spark master machine (host machine)
  - [configure_master](./roles/configure_master/tasks/main.yml): install relevant packages for the spark host machine

### `deploy_services.yml`

- Deploy Spark

  - [install spark and java](./roles/spark_install/tasks/main.yml): install spark, java and move spark to `/opt/spark/`
  - [configure_spark](./roles/configure_spark/tasks/main.yml): give user ec2-user permission to read and write to `/opt/spark`

- Start service on the host machine

  - [spark_host](./roles/spark_host/tasks/main.yml): start the spark master on the host machine
  - [deploy_monitoring](./roles/deploy_monitoring/tasks/main.yml): download promethus and grafana on host machine
  - [deploy_prefect](./roles/deploy_prefect/tasks/main.yml): deploy prefect server on the host machine

- Start service on the working machines

  - [spark_worker](./roles/spark_worker/tasks/main.yml): let workers connect to spark master
  - [install_nodeexporter](./roles/install_nodeexporter/tasks/main.yml): install node exporter on working machines

- deploy postgre sql and prefect on client machine (spark driver)
  - [deploy_postgre](./roles/deploy_postgre/tasks/main.yml): deploy postgre sql on the client machine and create db user and database `coursework`
  - [connect_prefect](./roles/connect_prefect/tasks/main.yml): connect to the prefect server so that all the pipeline on client machines can be monitored
