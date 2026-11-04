import { LogForwarder, LogLevel, LogEntry } from './logging'

describe('LogForwarder', () => {
  it('buffers entries and flushes them', () => {
    const flushed: LogEntry[][] = []
    const forwarder = new LogForwarder((entries) => flushed.push(entries), 'debug')

    forwarder.log('info', 'hello')
    forwarder.log('warn', 'world')
    expect(flushed).toHaveLength(0)  // not flushed yet

    forwarder.flush()
    expect(flushed).toHaveLength(1)
    expect(flushed[0]).toHaveLength(2)
    expect(flushed[0][0].message).toBe('hello')
    expect(flushed[0][1].message).toBe('world')
  })

  it('auto-flushes on error level', () => {
    const flushed: LogEntry[][] = []
    const forwarder = new LogForwarder((entries) => flushed.push(entries), 'debug')

    forwarder.log('info', 'before error')
    forwarder.log('error', 'boom')
    expect(flushed).toHaveLength(1)
    expect(flushed[0]).toHaveLength(2)
  })

  it('respects minLevel filter', () => {
    const flushed: LogEntry[][] = []
    const forwarder = new LogForwarder((entries) => flushed.push(entries), 'warn')

    forwarder.log('debug', 'ignored')
    forwarder.log('info', 'also ignored')
    forwarder.log('warn', 'included')
    forwarder.flush()

    expect(flushed[0]).toHaveLength(1)
    expect(flushed[0][0].message).toBe('included')
  })

  it('does nothing on flush when buffer is empty', () => {
    const flushed: LogEntry[][] = []
    const forwarder = new LogForwarder((entries) => flushed.push(entries), 'debug')
    forwarder.flush()
    expect(flushed).toHaveLength(0)
  })
})
