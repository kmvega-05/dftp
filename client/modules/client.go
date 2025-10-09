package modules

import (
	"bufio"
	"fmt"
	"net"
)

type Client struct {
	AddressIP string
	Port      string
	Conn      net.Conn
	Reader    *bufio.Reader
}

func NewClient(addressIp, port string) *Client {
	return &Client{
		AddressIP: addressIp,
		Port:      port,
	}
}

func (c *Client) Connect() error {
	address := c.AddressIP + ":" + c.Port
	conn, err := net.Dial("tcp", address)
	if err != nil {
		return fmt.Errorf("error al conectar con el servidor: %w", err)
	}
	c.Conn = conn
	c.Reader = bufio.NewReader(conn)
	_, err = c.Reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("error al leer mensaje de bienvenida: %w", err)
	}
	return nil
}

func (c *Client) Close() error {
	if c.Conn != nil {
		return c.Conn.Close()
	}
	return nil
}

func (c *Client) SendCommand(command string) (string, error) {
	_, err := c.Conn.Write([]byte(command + "\r\n"))
	if err != nil {
		return "", err
	}
	resp, err := c.Reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	return resp, nil
}
