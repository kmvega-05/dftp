package modules

import (
	"bufio"
	"fmt"
	"net"
	"strings"
)

type Client struct {
	AddressIP   string
	Port        string
	ControlConn net.Conn
	DataConn    net.Conn
	PassiveMode bool
	Reader      *bufio.Reader
	Writer      *bufio.Writer
}

func NewClient(addressIp, port string) *Client {
	return &Client{
		AddressIP:   addressIp,
		Port:        port,
		PassiveMode: true,
	}
}

func (c *Client) Connect() error {
	address := c.AddressIP + ":" + c.Port
	conn, err := net.Dial("tcp", address)
	if err != nil {
		return fmt.Errorf("error al conectar con el servidor: %w", err)
	}
	c.ControlConn = conn
	c.Reader = bufio.NewReader(conn)
	c.Writer = bufio.NewWriter(conn)

	_, err = c.Reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("error al leer mensaje de bienvenida: %w", err)
	}
	return nil
}

func (c *Client) Close() {
	if c.ControlConn != nil {
		c.ControlConn.Close()
	}
	if c.DataConn != nil {
		c.DataConn.Close()
	}
}

func (c *Client) SendCommand(command string) error {
	fmt.Printf("Client: %s", command)
	_, err := c.ControlConn.Write([]byte(command + "\r\n"))
	if err != nil {
		return err
	}
	return c.Writer.Flush()
}

func (c *Client) ReadResponse() (string, error) {
	resp, err := c.Reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(resp), err
}
