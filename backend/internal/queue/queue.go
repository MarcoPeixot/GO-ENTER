package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"

	"juridicflow/internal/documents"
)

// Publisher publishes document jobs to a durable RabbitMQ queue.
type Publisher struct {
	conn      *amqp.Connection
	channel   *amqp.Channel
	queueName string
}

func NewPublisher(url, queueName string) (*Publisher, error) {
	conn, err := amqp.Dial(url)
	if err != nil {
		return nil, fmt.Errorf("dial rabbitmq: %w", err)
	}
	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("open channel: %w", err)
	}
	if _, err := ch.QueueDeclare(queueName, true, false, false, false, nil); err != nil {
		ch.Close()
		conn.Close()
		return nil, fmt.Errorf("declare queue: %w", err)
	}
	return &Publisher{conn: conn, channel: ch, queueName: queueName}, nil
}

// Publish sends a job to the worker queue as a persistent JSON message.
func (p *Publisher) Publish(ctx context.Context, job documents.Job) error {
	body, err := json.Marshal(job)
	if err != nil {
		return fmt.Errorf("marshal job: %w", err)
	}
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	return p.channel.PublishWithContext(ctx, "", p.queueName, false, false, amqp.Publishing{
		ContentType:  "application/json",
		DeliveryMode: amqp.Persistent,
		Timestamp:    time.Now(),
		Body:         body,
	})
}

func (p *Publisher) Close() {
	if p.channel != nil {
		p.channel.Close()
	}
	if p.conn != nil {
		p.conn.Close()
	}
}
