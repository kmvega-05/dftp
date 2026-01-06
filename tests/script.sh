docker build -t dftp .

# Discovery Node
docker run  --rm --name discovery1 --net dftp_net --ip 172.25.0.2 -v $(pwd):/app dftp tests/run_discovery.py --id discovery1 --ip 172.25.0.2 --port 9000
docker run  --rm --name discovery2 --net dftp_net --ip 172.25.0.3 -v $(pwd):/app dftp tests/run_discovery.py --id discovery2 --ip 172.25.0.3 --port 9000
docker run  --rm --name discovery3 --net dftp_net --ip 172.25.0.4 -v $(pwd):/app dftp tests/run_discovery.py --id discovery3 --ip 172.25.0.4 --port 9000

# Auth Node
docker run --rm --name auth1 --net dftp_net --ip 172.25.0.5 -v $(pwd):/app dftp tests/run_auth.py --id auth1 --ip 172.25.0.5 --port 9000
docker run --rm --name auth2 --net dftp_net --ip 172.25.0.6 -v $(pwd):/app dftp tests/run_auth.py --id auth2 --ip 172.25.0.6 --port 9000
docker run --rm --name auth3 --net dftp_net --ip 172.25.0.7 -v $(pwd):/app dftp tests/run_auth.py --id auth3 --ip 172.25.0.7 --port 9000

# Processing Node
docker run --rm --name processing1 --net dftp_net --ip 172.25.0.8 -v $(pwd):/app dftp tests/run_processing.py --id processing1 --ip 172.25.0.8 --port 9000
docker run --rm --name processing2 --net dftp_net --ip 172.25.0.9 -v $(pwd):/app dftp tests/run_processing.py --id processing2 --ip 172.25.0.9 --port 9000
docker run --rm --name processing3 --net dftp_net --ip 172.25.0.10 -v $(pwd):/app dftp tests/run_processing.py --id processing3 --ip 172.25.0.10 --port 9000

# Routing Node
docker run --rm --name routing1 --net dftp_net --ip 172.25.0.11 -p 2121:21 -v $(pwd):/app dftp tests/run_routing.py --id routing1 --ip 172.25.0.11 --ftp-port 21 --internal-port 9000
docker run --rm --name routing2 --net dftp_net --ip 172.25.0.12 -p 2122:21 -v $(pwd):/app dftp tests/run_routing.py --id routing2 --ip 172.25.0.12 --ftp-port 21 --internal-port 9000
docker run --rm --name routing3 --net dftp_net --ip 172.25.0.13 -p 2123:21 -v $(pwd):/app dftp tests/run_routing.py --id routing3 --ip 172.25.0.13 --ftp-port 21 --internal-port 9000

# Data Node
docker run --rm --name data1 --net dftp_net --ip 172.25.0.14 -v $(pwd):/app dftp tests/run_data.py --id data1 --ip 172.25.0.14 --port 9000
docker run --rm --name data2 --net dftp_net --ip 172.25.0.15 -v $(pwd):/app dftp tests/run_data.py --id data2 --ip 172.25.0.15 --port 9000
docker run --rm --name data3 --net dftp_net --ip 172.25.0.16 -v $(pwd):/app dftp tests/run_data.py --id data3 --ip 172.25.0.16 --port 9000

# Cliente en terminal
docker run --rm -it --network host debian:stable-slim bash -c "apt-get update && apt-get install -y telnet && bash"
