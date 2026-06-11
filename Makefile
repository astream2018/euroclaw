.PHONY: install up down run clean

install:
	pip install -r requirements.txt

up:
	docker-compose up -d

down:
	docker-compose down

run:
	uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f /tmp/firecracker-*.socket
	rm -f /tmp/rootfs-*.ext4