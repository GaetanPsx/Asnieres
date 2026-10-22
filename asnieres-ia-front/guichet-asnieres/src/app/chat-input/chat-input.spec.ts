import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ChatInputComponent } from './chat-input';

describe('ChatInputComponent', () => {
  let component: ChatInputComponent;
  let fixture: ComponentFixture<ChatInputComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatInputComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatInputComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should fill the prompt when a suggestion is selected without submitting it', () => {
    const submitted: string[] = [];
    component.submitted.subscribe((value) => submitted.push(value));

    const suggestion = component.suggestions[0];
    component.selectSuggestion(suggestion.prompt);
    fixture.detectChanges();

    const textarea = fixture.nativeElement.querySelector('textarea') as HTMLTextAreaElement;
    expect(textarea.value).toBe(suggestion.prompt);
    expect(submitted).toEqual([]);
  });
});
