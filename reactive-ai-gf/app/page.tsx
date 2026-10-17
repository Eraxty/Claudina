export default function Home() {
  return (
    <main>
      <header>
        <div className="avatar">C</div>
        <div>
          <h1>Claudina</h1>
          <small>Active now</small>
        </div>
      </header>

      <div className="chat">
        <p>hey, how are you?</p>
        <p className="mine">i'm good. how was your day?</p>
        <p>pretty calm. i just wanted to talk to you.</p>
      </div>

      <form>
        <input placeholder="Message Claudina..." />
        <button>Send</button>
      </form>
    </main>
  );
}