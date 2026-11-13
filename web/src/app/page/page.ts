import { Component, input } from '@angular/core';

@Component({
  selector: 'app-page',
  imports: [],
  templateUrl: './page.html',
  styleUrl: './page.scss',
})
export class Page {
  title = input.required<string>();
}