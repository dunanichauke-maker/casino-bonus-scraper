import { Component, OnInit } from '@angular/core';

interface BonusRecord {
  casino_name: string;
  welcome_bonus: string;
  wagering_requirement: number | null;
  minimum_deposit: number | null;
  source_url: string;
  last_updated?: string | null;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  title = 'Casino Bonus Snapshot';
  bonuses: BonusRecord[] = [];
  loading = true;
  error = '';

  ngOnInit(): void {
    fetch('assets/bonuses.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load data (${response.status})`);
        }
        return response.json();
      })
      .then((data: BonusRecord[]) => {
        this.bonuses = data;
      })
      .catch(() => {
        this.error = 'Unable to load bonus data. Run the scraper to generate the JSON file.';
      })
      .finally(() => {
        this.loading = false;
      });
  }

  formatWagering(value: number | null): string {
    return value === null ? 'Not available' : `${value}x`;
  }

  formatDeposit(value: number | null): string {
    if (value === null) {
      return 'Not available';
    }
    return `$${value.toFixed(2)}`;
  }
}
