FROM golang:1.22 

WORKDIR /app

COPY server/ ./

RUN go build -o ftp-server .

RUN mkdir -p /configs

EXPOSE 21
EXPOSE 20

CMD ["./ftp-server"]