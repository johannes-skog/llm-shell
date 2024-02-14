docker-compose/build:
	@docker-compose build

docker-compose/down:
	@docker-compose stop
	@docker-compose down

docker-compose/up: docker-compose/build
	@docker-compose up -d
