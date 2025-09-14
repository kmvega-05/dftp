FROM golang:1.24 

WORKDIR /app

COPY server/go.mod server/go.sum ./
RUN go mod download

COPY server/ ./

RUN go build -o ftp-server .

RUN mkdir -p /configs

EXPOSE 21

CMD ["./ftp-server"]