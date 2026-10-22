import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the welcome prompt before the conversation starts', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h2')?.textContent).toContain('Comment la Mairie d\'Asnières peut-elle vous aider ?');
  });

  it('should display the sent question in the conversation', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.handlePrompt('Quels sont les horaires de la mairie ?');
    fixture.detectChanges();
    await fixture.whenStable();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Quels sont les horaires de la mairie ?');
    expect(compiled.textContent).toContain("La réponse à votre question s'affichera ici");
  });

  it('should return to the home page from a conversation', async () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.handlePrompt('Quels sont les horaires de la mairie ?');
    fixture.detectChanges();

    app.returnToHome();
    fixture.detectChanges();
    await fixture.whenStable();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h2')?.textContent).toContain('Comment la Mairie d\'Asnières peut-elle vous aider ?');
    expect(compiled.textContent).not.toContain('Quels sont les horaires de la mairie ?');
  });
});
