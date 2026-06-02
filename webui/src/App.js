// App — ConnectedFlow only (DesignCanvas dropped).
// 6 screens routed by state; bottom nav clicks dispatch through data-nav-target.

function ConnectedFlow() {
  const [route, setRoute] = React.useState('home');
  const [song, setSong] = React.useState(null);

  React.useEffect(() => {
    const onClick = (e) => {
      const el = e.target.closest('[data-nav-target]');
      if (!el) return;
      setRoute(el.getAttribute('data-nav-target'));
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  return (
    <Phone>
      {route === 'home' && (
        <HomeScreen onPickSong={(s) => { setSong(s); setRoute('setup'); }}/>
      )}
      {route === 'setup' && (
        <SetupScreen song={song} onBack={() => setRoute('home')} onStart={() => setRoute('practice')}/>
      )}
      {route === 'practice' && (
        <PracticeScreen song={song} onBack={() => setRoute('setup')} onEnd={() => setRoute('review')}/>
      )}
      {route === 'review' && (
        <ReviewScreen song={song} onDone={() => setRoute('home')} onRetry={() => setRoute('practice')}/>
      )}
      {route === 'history' && <HistoryScreen/>}
      {route === 'profile' && <ProfileScreen/>}
    </Phone>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<ConnectedFlow/>);
