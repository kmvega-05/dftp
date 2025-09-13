FROM golang:1.21-alpine

WORKDIR /app

COPY src/server/ ./

RUN go build -o ftp-server .

RUN mkdir -p /data

COPY src/server/data/users.json /data/users.json

EXPOSE 21
EXPOSE 20

CMD ["./ftp-server"]