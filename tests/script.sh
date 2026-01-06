docker build -t dftp .

# Discovery Node
docker run  --rm --name discovery1 --net dftp_net  -v $(pwd):/app dftp tests/run_discovery.py --id discovery1 --port 9000
docker run  --rm --name discovery2 --net dftp_net  -v $(pwd):/app dftp tests/run_discovery.py --id discovery2 --port 9000
docker run  --rm --name discovery3 --net dftp_net  -v $(pwd):/app dftp tests/run_discovery.py --id discovery3 --port 9000

# Auth Node
docker run --rm --name auth1 --net dftp_net -v $(pwd):/app dftp tests/run_auth.py --id auth1 --port 9000
docker run --rm --name auth2 --net dftp_net -v $(pwd):/app dftp tests/run_auth.py --id auth2 --port 9000
docker run --rm --name auth3 --net dftp_net -v $(pwd):/app dftp tests/run_auth.py --id auth3 --port 9000

# Processing Node
docker run --rm --name processing1 --net dftp_net -v $(pwd):/app dftp tests/run_processing.py --id processing1 --port 9000
docker run --rm --name processing2 --net dftp_net -v $(pwd):/app dftp tests/run_processing.py --id processing2 --port 9000
docker run --rm --name processing3 --net dftp_net -v $(pwd):/app dftp tests/run_processing.py --id processing3 --port 9000

# Routing Node
docker run --rm --name routing1 --net dftp_net -p 2121:21 -v $(pwd):/app dftp tests/run_routing.py --id routing1 --port 9000
docker run --rm --name routing2 --net dftp_net -p 2122:21 -v $(pwd):/app dftp tests/run_routing.py --id routing2 --port 9000
docker run --rm --name routing3 --net dftp_net -p 2123:21 -v $(pwd):/app dftp tests/run_routing.py --id routing3 --port 9000

# Data Node
docker run --rm --name data1 --net dftp_net -v $(pwd):/app dftp tests/run_data.py --id data1 --port 9000
docker run --rm --name data2 --net dftp_net -v $(pwd):/app dftp tests/run_data.py --id data2 --port 9000
docker run --rm --name data3 --net dftp_net -v $(pwd):/app dftp tests/run_data.py --id data3 --port 9000

# Cliente en terminal
docker run --rm -it --network host debian:stable-slim bash -c "apt-get update && apt-get install -y telnet && bash"
