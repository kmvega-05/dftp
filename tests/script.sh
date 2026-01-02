docker build -t dftp .

# Discovery Node
docker run  --rm --name discovery1 --net dftp_net --ip 172.25.0.2 -v $(pwd):/app dftp tests/run_discovery.py --id discovery1 --ip 172.25.0.2 --port 9000

# Auth Node
docker run --rm --name auth1 --net dftp_net --ip 172.25.0.3 -v $(pwd):/app dftp tests/run_auth.py --id auth1 --ip 172.25.0.3 --port 9000

# Processing Node
docker run --rm --name processing1 --net dftp_net --ip 172.25.0.4 -v $(pwd):/app dftp tests/run_processing.py --id processing1 --ip 172.25.0.4 --port 9000

# Routing Node
docker run --rm --name routing1 --net dftp_net --ip 172.25.0.5 -p 2121:21 -v $(pwd):/app dftp tests/run_routing.py --id routing1 --ip 172.25.0.5 --ftp-port 21 --internal-port 9000

# Data Node
docker run -d --rm --name data1 --net dftp_net --ip 172.25.0.6 -v $(pwd):/app dftp tests/run_data.py --id data1 --ip 172.25.0.6 --port 9000