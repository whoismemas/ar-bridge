.PHONY: run test clean

run:
	python3.9 ar_bridge.py

test:
	curl -s http://127.0.0.1:20132/health

clean:
	@echo "no build artifacts"
